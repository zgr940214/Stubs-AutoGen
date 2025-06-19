from pycparser import parse_file, c_ast
from collections import deque
import sys

class Notifier:
    def __init__(self):
        self._signatures: dict[str, str] = {}
        self._pending: set[str] = set()

    def add_signature(self, name: str, ret_type: str) -> None:
        self._signatures[name] = ret_type
        self._pending.discard()

class ScopeStack:
    def __init__(self):
        self.stack = deque([{}])  # initialize with empty global scope

    def push_scope(self):
        self.stack.append({})

    def pop_scope(self):
        self.stack.pop()

    def add_variable(self, name, typename):
        self.stack[-1][name] = typename

    def find_type(self, name):
        for scope in reversed(self.stack):
            if name in scope:
                return scope[name]
        return "void"  # fallback

class ScopedVisitor(c_ast.NodeVisitor):
    def __init__(self, scope_stack, stub_list_file):
        self.scope_stack = scope_stack
        path = Path(stub_list_file)
        self.stub_nl = path.read_text(encoding="utf-8").splitlines()
        self.stub_output_list = []

    def visit_Decl(self, node):
        if isinstance(node.type, c_ast.TypeDecl):
            typename = " ".join(node.type.type.names)  # e.g. "int", "unsigned int"
            self.scope_stack.add_variable(node.name, typename)
        elif isinstance(node.type, c_ast.PtrDecl) and isinstance(node.type.type, c_ast.TypeDecl):
            typename = " ".join(node.type.type.type.names) + " *"
            self.scope_stack.add_variable(node.name, typename)

    def visit_Compound(self, node):
        self.scope_stack.push_scope()
        for stmt in node.block_items or []:
            self.visit(stmt)
        self.scope_stack.pop_scope()

    def visit_Return(self, node: c_ast.Return):
        """
                If return <expr>; where <expr> is a FuncCall with no type,
                assign the surrounding function's return type as best guess.
                """
        if isinstance(node.expr, c_ast.FuncCall) and isinstance(node.expr.name, c_ast.ID):
            callee = node.expr.name.name
            # 1) already known? nothing to do
            if self.cbreg.resolve(callee):
                return
            # 2) fall back to surrounding function's type (heuristic)
            if self._cur_func_ret:
                self.cbreg.deliver(callee, self._cur_func_ret)  # publish immediately
                # Optional: mark it as 'inferred' vs 'declared'
        self.generic_visit(node)

    def parse_expression_type(self, node):
        return "void"

    def parse_func_signature(self, node):
        if node.name.name not in self.stub_nl:
            return
        ret_type = []
        arg_names = []
        params_type = []
        if node.args:
            for expr in node.args.exprs:
                if isinstance(expr, c_ast.ID):
                    arg_names.append(expr.name)
                else:
                    # imm / literal string / nested function call
                    # for imm/string , we try to guess its type
                    # nested function call, we would attach a callback funciton
                    # which would be called after that function node has been parsed
                    # and cb will write back its return value's type to our funciton signature structure
                    arg_names.append(self.parse_expression_type(self, node))
            for arg_name in arg_names:
                params_type.append(self.scope_stack.find_type(arg_name))
        else: #void arg
            params_type.append("void")

        return

    def visit_FuncDef(self, node):
        self.scope_stack.push_scope()
        if isinstance(node.decl.type, c_ast.FuncDecl) and node.decl.type.args:
            for param in node.decl.type.args.params:
                if isinstance(param.type, c_ast.TypeDecl):
                    typename = " ".join(param.type.type.names)
                    self.scope_stack.add_variable(param.name, typename)
                elif isinstance(param.type, c_ast.PtrDecl) and isinstance(param.type.type, c_ast.TypeDecl):
                    typename = " ".join(param.type.type.type.names) + " *"
                    self.scope_stack.add_variable(param.name, typename)
        self.visit(node.body)
        self.scope_stack.pop_scope()



TEMPLATE = """\
#include "{header}"
{functions}
"""

FUNC_STUB_VOID = """\
{ret} {name}({params}) {{
    (void){dummy};
}}
"""

FUNC_STUB_NONVOID = """\
{ret} {name}({params}) {{
    (void){dummy};
    return 0;
}}
"""

def parse_stubs(stub_list):
    for ret, name, params in stub_list:
        params = params.strip() or "void"
        # 去除可变参数 '...'
        param_list = [
            p.strip() for p in params.split(",") if p.strip() and p.strip() != "..."
        ]
        dummy = ", ".join(p.split()[-1] for p in param_list if p != "void") or "0"
        if ret.strip() == "void":
            yield FUNC_STUB_VOID.format(ret=ret, name=name, params=params, dummy=dummy)
        else:
            yield FUNC_STUB_NONVOID.format(
                ret=ret, name=name, params=params, dummy=dummy
            )

def gen_stubs(stub_list, file):
    file.write_text()
    stubs = list(parse_stubs(stub_list))
    out_file.write_text(
        TEMPLATE.format(header=header_path.name, functions="\n".join(stubs)),
        encoding="utf-8",
    )
    print(f"✅ Stub 生成完毕: {out_file}")

# 用于测试作用域分析是否正确
def analyze_scopes(filename):
    ast = parse_file(filename, use_cpp=True, cpp_path=r"C:/Users/zhoueric/Desktop/gcc-arm-none-eabi-10.3-2021.10/bin/arm-none-eabi-gcc.exe", cpp_args=['-E', r'-Iutils/fake_libc_include'])
    scope_stack = ScopeStack()
    visitor = ScopedVisitor(scope_stack)
    visitor.visit(ast)
    print("Scope stack analysis complete (no runtime errors).")

# 使用示例（你可以把路径换成自己的测试用C文件）
# analyze_scopes("test.c")
# Run logic as module
def analyze_and_stub(filename, generate_stub, stub_name_list):
    ast = parse_file(filename, use_cpp=True,
                     cpp_path=r"C:/Users/zhoueric/Desktop/gcc-arm-none-eabi-10.3-2021.10/bin/arm-none-eabi-gcc.exe",
                     cpp_args='-E -Iutils/fake_libc_include')

    ScopedFuncVisitor().visit(ast)
    call_visitor = ScopedFuncCallVisitor()
    call_visitor.visit(ast)

    return [generate_stub(fname, args, stub_name_list)
            for fname, args in call_visitor.stubs.items()]


if __name__ == '__main__':
    # if len(sys.argv) != 2:
    #     print(f'用法: python {sys.argv[0]} source.c')
    #     sys.exit(1)

    # filename = sys.argv[1]
    # ast = analyze_and_stub(filename, use_cpp=True,
    #                     cpp_path=r"C:/Users/zhoueric/Desktop/gcc-arm-none-eabi-10.3-2021.10/bin/arm-none-eabi-gcc.exe",
    #                  cpp_args=['-E', r'-Iutils/fake_libc_include'])

    # stubs = extract_stubs(ast)

    # print("需要生成Stub的函数签名列表：")
    # for func in sorted(stubs):
    #     print(generate_stub_signature(func))