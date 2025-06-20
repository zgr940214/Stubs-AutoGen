import scope_analyzer as sa
import stub_parser as sp

# ───────────────────────────── Parse & generate stubs from cfiles/headers in batch ────────────────────────────
def parse_batch(cfiles, cheaders, gcc):
    target_stubs = sp.parse_stubs(cfiles, cheaders)

    for cfile in cfiles:
        run(cfile, target_stubs, gcc, Path(cfile).stem)

# ───────────────────────────── Main ────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="需要生成stub的源文件,以及对应的头文件")
    parser.add_argument('-c', '--sources', nargs='+', required=True, help='C源文件或目录')
    parser.add_argument('-H', '--headers', nargs='+', required=True, help='头文件或目录')
    parser.add_argument("-t", '--tool-chain', nargs='+', required=True, help="GCC tool chain bin directory")
    args = parser.parse_args()

    parse_batch(args.sources, args.headers, args.tool_chain)
    