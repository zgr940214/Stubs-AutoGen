from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from pycparser import parse_file, c_ast
import pycparser.c_ast as AST

import argparse
import sys
import os

# ──────────────────────────────── 1  Data models ────────────────────────────────
Callback = Callable[[str], None]           # cb(new_ret_type)

@dataclass
class StubInfo:
    """Metadata for a function that may need a stub."""
    is_stub: bool
    ret_type: str                # may start as "void*"
    param_types: List[str] = field(default_factory=list)
    _cbs: List[Callback] = field(default_factory=list, repr=False)

    # register / fire
    def add_cb(self, cb: Callback) -> None:       self._cbs.append(cb)
    def fire(self, real: str) -> None:
        self.ret_type = real
        for cb in self._cbs: cb(real)
        self._cbs.clear()

    def post_fire(self):
        for cb in self._cbs: cb(self.ret_type)
        self._cbs.clear()

@dataclass
class ScopeFrame:
    symbols: Dict[str, str] = field(default_factory=dict)
    is_func: bool = False
    ret_type: Optional[str] = None


class ScopeStack:
    def __init__(self) -> None:
        self._stack: List[ScopeFrame] = [ScopeFrame()]           # global

    # helpers -------------------------------------------------------------------
    def push_block(self) -> None:                       self._stack.append(ScopeFrame())
    def push_func(self, ret: str) -> None:              self._stack.append(ScopeFrame(is_func=True, ret_type=ret))
    def pop(self) -> None:                              self._stack.pop()

    def add_var(self, name: str, typ: str) -> None:     self._stack[-1].symbols[name] = typ
    def find_var(self, name: str) -> Optional[str]:
        for frame in reversed(self._stack):
            if name in frame.symbols: return frame.symbols[name]
        return None

    def enclosing_ret(self) -> Optional[str]:
        for frame in reversed(self._stack):
            if frame.is_func: return frame.ret_type
        return None


# ───────────────────────────── 2  Expression inference ──────────────────────────
def infer_expr_type(expr: c_ast.Node,
                    scope: ScopeStack,
                    stubs: Dict[str, StubInfo]) -> str:
    """Very small subset: ID / address-of / nested FuncCall. Expand as needed."""
    if isinstance(expr, c_ast.ID):
        return scope.find_var(expr.name) or "void*"

    if isinstance(expr, c_ast.UnaryOp) and expr.op == "&":
        base = infer_expr_type(expr.expr, scope, stubs)
        return f"{base} *"

    if isinstance(expr, c_ast.FuncCall) and isinstance(expr.name, c_ast.ID):
        fname = expr.name.name
        info = stubs.get(fname)
        if info: return info.ret_type
        # unknown → register placeholder
        stubs[fname] = StubInfo(is_stub=True, ret_type="void*", param_types=[])
        return "void*"

    return "int"          # fallback


def type_to_str(t) -> str:
    """
    Recursively convert a pycparser type node into a readable C-type string.
    Handles PtrDecl / ArrayDecl / FuncDecl / TypeDecl wrappers.
    """

    # ---------- 基类型 ----------
    if isinstance(t, AST.IdentifierType):      # int, uint8_t, size_t, typedef ...
        return ' '.join(t.names)

    if isinstance(t, AST.Struct):
        return f'struct {t.name or "anon"}'

    if isinstance(t, AST.Union):
        return f'union {t.name or "anon"}'

    if isinstance(t, AST.Enum):
        return f'enum {t.name or "anon"}'

    # ---------- 包装层 ----------
    # typedef / plain declarator：继续往里拆
    if isinstance(t, AST.TypeDecl):
        return type_to_str(t.type)

    # 指针
    if isinstance(t, AST.PtrDecl):
        return type_to_str(t.type) + '*'

    # 数组（忽略维度表达式，只加 []）
    if isinstance(t, AST.ArrayDecl):
        base = type_to_str(t.type)
        dim  = t.dim.value if t.dim else ''
        return f'{base}[{dim}]'

    # 函数指针 / 原型
    if isinstance(t, AST.FuncDecl):
        ret = type_to_str(t.type)
        if t.args:                # 可能是空形参列表
            params = ', '.join(type_to_str(p.type) for p in t.args.params)
        else:
            params = ''
        return f'{ret} ({params})'

    # 未覆盖的类型——兜底
    return t.__class__.__name__
# ─────────────────────────── 3  Main visitor (single TU) ─────────────────────────
class TUVisitor(c_ast.NodeVisitor):
    def __init__(self, stub_whitelist: Sequence[str]) -> None:
        self.scope = ScopeStack()
        self.stubs: Dict[str, StubInfo] = {}
        self.interesting = set(stub_whitelist)

    # --- declarations (vars / params) -----------------------------------------
    def visit_Decl(self, node: c_ast.Decl):
        typ = type_to_str(node.type)
        self.scope.add_var(node.name, typ)
        self.generic_visit(node)

    # --- function body --------------------------------------------------------
    def visit_FuncDef(self, node: c_ast.FuncDef):
        ret = type_to_str(node.decl.type.type)       # rough stringify
        self.scope.push_func(ret)
        # put parameters into scope
        if node.decl.type.args:
            for p in node.decl.type.args.params:
                pname = p.name
                ptype = type_to_str(p.type)
                self.scope.add_var(pname, ptype)

        self.generic_visit(node.body)
        self.scope.pop()

    # --- plain block ----------------------------------------------------------
    def visit_Compound(self, node):          # override to manage block scope
        self.scope.push_block()
        for stmt in node.block_items or []:
            self.visit(stmt)
        self.scope.pop()

    # --- function call --------------------------------------------------------
    def visit_FuncCall(self, node: c_ast.FuncCall):
        if not isinstance(node.name, c_ast.ID):  # func ptr etc.
            return self.generic_visit(node)

        fname = node.name.name
        if fname not in self.interesting:       # ignore internal calls
            return self.generic_visit(node)

        # param types
        param_types: List[str] = []
        if node.args:
            for arg in node.args.exprs:
                param_types.append(infer_expr_type(arg, self.scope, self.stubs))
        else:
            param_types.append("void")

        # upsert
        info = self.stubs.get(fname)
        if info:
            info.param_types = param_types
        else:
            self.stubs[fname] = StubInfo(is_stub=True, ret_type="void*", param_types=param_types)

        # continue into arguments (important for nested calls)
        self.generic_visit(node)

    # --- return heuristic -----------------------------------------------------
    def visit_Return(self, node: c_ast.Return):
        if isinstance(node.expr, c_ast.FuncCall) and isinstance(node.expr.name, c_ast.ID):
            callee = node.expr.name.name
            if callee in self.interesting and callee not in self.stubs:
                guessed = self.scope.enclosing_ret()
                self.stubs[callee] = StubInfo(is_stub=True, ret_type=guessed or "void*", param_types=[])
        self.generic_visit(node)


# ─────────────────────────── 4  Emit stub C source  ────────────────────────────
STUB_TEMPLATE = """\
{ret} {name}({params}) {{
    (void){dummy};
{ret_stmt}}}
"""

def emit_stubs(stubs: Dict[str, StubInfo], out_path: Path) -> None:
    pieces = []
    for name, info in stubs.items():
        if not info.is_stub:                   # skip defined functions
            continue
        params = ", ".join(info.param_types) or "void"
        dummy = ", ".join(f"arg{i}" for i, _ in enumerate(info.param_types)) or "0"
        ret_stmt = "" if info.ret_type.strip() == "void" else "    return 0;"
        pieces.append(STUB_TEMPLATE.format(ret=info.ret_type,
                                           name=name,
                                           params=params,
                                           dummy=dummy,
                                           ret_stmt=ret_stmt))
    out_path.write_text("\n\n".join(pieces), encoding="utf-8")
    print("Stub file written →", out_path)


# ───────────────────────────── 5  End-to-end driver ────────────────────────────
def run(source: str, stub_list_file: str, cpp_path: str):
    whitelist = Path(stub_list_file).read_text(encoding="utf-8").splitlines()
    ast = parse_file(source,
                     use_cpp=True,
                     cpp_path=cpp_path,
                     cpp_args = [
                        '-E',                                  # 只预处理
                        '-nostdinc',                           # 不用 GCC 自带头
                        r'-IC:/Users/zhoueric/Desktop/tools/venv/Lib/site-packages'
                        r'/pycparser_fake_libc',   # ← 原始字符串
                        '-D__attribute__(x)=',
                        '-D__extension__=',
                        '-D__asm__(x)=',
                    ])

    vis = TUVisitor(whitelist)
    vis.visit(ast)

    emit_stubs(vis.stubs, Path("autostubs.c"))


if __name__ == "__main__":
    # python stubgen.py <file.c> <stub_names.txt> <path-to-gcc>
    src, names, gcc = sys.argv[1:]
    run(src, names, gcc)