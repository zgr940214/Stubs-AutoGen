#!/usr/bin/env python3
import argparse
import re
from pathlib import Path
from typing import Set

# 正则表达式
FUNC_CALL_RE = re.compile(r'\b(\w+)\s*\(', re.MULTILINE)
FUNC_DEF_RE = re.compile(r'^[\w\s\*\(\)]+?\s+(\w+)\s*\([^;]*?\)\s*\{', re.MULTILINE)
FUNC_DECL_RE = re.compile(r'^[\w\s\*\(\)]+?\s+(\w+)\s*\([^;]*?\)\s*;', re.MULTILINE)

# 提取文件中的函数调用
def extract_calls(code: str) -> Set[str]:
    return set(FUNC_CALL_RE.findall(code))

# 提取文件中的函数定义
def extract_defs(code: str) -> Set[str]:
    return set(FUNC_DEF_RE.findall(code))

# 提取头文件中的函数声明
def extract_decls(code: str) -> Set[str]:
    return set(FUNC_DECL_RE.findall(code))

# 收集指定路径下所有的.c/.h文件
def collect_files(paths: list, extensions: Set[str]) -> Set[Path]:
    files = set()
    for path in paths:
        p = Path(path)
        if p.is_dir():
            files.update(p.rglob("*"))
        elif p.is_file():
            files.add(p)
    return {f for f in files if f.suffix in extensions}

def parse_stubs(c_file_paths, h_file_paths):
    c_files = collect_files(c_file_paths)
    h_files = collect_files(h_file_paths)

    all_calls, all_defs, all_decls = set(), set(), set()
    for file in c_files:
        code = file.read_text(encoding='utf-8', errors='ignore')
        all_calls |= extract_calls(code)
        all_defs |= extract_defs(code)

    for file in h_files:
        code = file.read_text(encoding='utf-8', errors='ignore')
        all_decls |= extract_decls(code)

    # 语言关键字过滤
    C_KEYWORDS = {
        'if', 'for', 'while', 'switch', 'return', 'sizeof', 'catch', 'typedef',
        'struct', 'union', 'else', 'case', 'do', 'goto', 'break', 'continue',
        'static', 'inline', 'extern'
    }
    stubs = sorted(all_calls - all_defs - all_decls - C_KEYWORDS)
    return stubs # return list


def main():
    parser = argparse.ArgumentParser(description="查找需要生成stub的外部函数调用")
    parser.add_argument('-c', '--sources', nargs='+', required=True, help='C源文件或目录')
    parser.add_argument('-H', '--headers', nargs='+', required=True, help='头文件或目录')
    parser.add_argument('-o', '--output', default='stubs.txt', help='输出文件 (默认: stubs.txt)')
    args = parser.parse_args()

    c_files = collect_files(args.sources, {'.c'})
    h_files = collect_files(args.headers, {'.h'})

    all_calls, all_defs, all_decls = set(), set(), set()

    for file in c_files:
        code = file.read_text(encoding='utf-8', errors='ignore')
        all_calls |= extract_calls(code)
        all_defs |= extract_defs(code)

    for file in h_files:
        code = file.read_text(encoding='utf-8', errors='ignore')
        all_decls |= extract_decls(code)

    # 语言关键字过滤
    C_KEYWORDS = {
        'if', 'for', 'while', 'switch', 'return', 'sizeof', 'catch', 'typedef',
        'struct', 'union', 'else', 'case', 'do', 'goto', 'break', 'continue',
        'static', 'inline', 'extern'
    }

    stubs = sorted(all_calls - all_defs - all_decls - C_KEYWORDS)

    if stubs:
        print("🔧 需要 Stub 的函数:")
        for stub in stubs:
            print(f" - {stub}")
        stub_file = Path(args.output)
        stub_file.write_text("\n".join(stubs), encoding='utf-8')
    else:
        print("✅ 没有需要生成stub的外部函数调用")

if __name__ == "__main__":
    main()