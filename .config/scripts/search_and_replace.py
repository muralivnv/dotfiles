#!/usr/bin/python3

# imports
import subprocess
from argparse import ArgumentParser, RawTextHelpFormatter
import sys

##### HELPFUL GIST
GIST = """
GREP: https://www.man7.org/linux/man-pages/man1/grep.1.html
    -n               : print line numbers
    -H               : print file name
    -i               : ignore case
    -l               : only-print file names that has matches
    --include \*.ext : match files with this extension
    -w               : match whole word
    -E               : extended regexp
    -r               : recursive

SED: https://www.gnu.org/software/sed/manual/sed.html
    -i    : in-place replace
    -n    : silent-mode
    -E    : extended regexp

    [ADDR] s/QUERY/REPLACE/[OPTIONS]
      ADDR
       #,{{#}}  : only match these lines
         $      : to final line
       /REGEXP/ : Any regexp
      OPTIONS
        # : number to match and replace every nth match in line
        g : match and replace all
        i : ignore case
        p : print lines that has matches

    [ADDR] [X]
      ADDR
       #,{{#}}  : only match these lines
         $      : to final line
       /REGEXP/ : Any regexp

      [X]
       i\TEXT  : insert text before line
       c\TEXT  : replace line with this text
       a\TEXT  : append text after line
       p       : print
       d       : delete

Combining Multiple Files Using SED:
    sed '$ s/$//' FILE1 FILE2 FILE3 ... > OUTFILE
"""
# constants
INTERACTIVE_CMD = """grep -l {GREP_FLAGS} "{QUERY}" | fzf --sort --reverse --preview='grep -n --color=always -C 2 {GREP_FLAGS} "{QUERY}" {}' --preview-window='up,70%:wrap' --ansi --bind="enter:execute(sed {SED_CMD} {}),shift-tab:up,tab:down" --cycle"""
NONINTERACTIVE_CMD = """grep -l {GREP_FLAGS} "{QUERY}" | xargs -I {} sh -c "sed {SED_CMD} {}" """
FZF_ERR_CODE_TO_IGNORE = [0, 1, 130]

#####
def trigger(parsed_args) -> None:
    full_cmd = None
    SED_CMD = parsed_args.SED_CMD.replace("{QUERY}", parsed_args.QUERY)
    SED_CMD = SED_CMD.replace("{REPLACE}", parsed_args.REPLACE)
    if parsed_args.no_interactive:
        full_cmd = NONINTERACTIVE_CMD.replace("{GREP_FLAGS}", parsed_args.GREP_FLAGS)
        full_cmd = full_cmd.replace("{QUERY}", parsed_args.QUERY)
        full_cmd = full_cmd.replace("{SED_CMD}", SED_CMD)
    else:
        full_cmd = INTERACTIVE_CMD.replace("{GREP_FLAGS}", parsed_args.GREP_FLAGS)
        full_cmd = full_cmd.replace("{QUERY}", parsed_args.QUERY)
        full_cmd = full_cmd.replace("{SED_CMD}", SED_CMD)
    try:
        subprocess.check_call(full_cmd, shell=True, stdout=sys.stdout, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        if not (e.returncode in FZF_ERR_CODE_TO_IGNORE):
            print(e)

if __name__ == "__main__":
    cli = ArgumentParser(formatter_class=RawTextHelpFormatter)

    cli.add_argument("--grep", type=str, dest="GREP_FLAGS", default="-r -w", help="-r -w", required=False)
    cli.add_argument("--sed", type=str, dest="SED_CMD", default='-i "s/{QUERY}/{REPLACE}/g"', help='-i "s/{QUERY}/{REPLACE}/g"', required=False)

    cli.add_argument("-q", type=str, dest="QUERY", help="QUERY", required= not "--gist" in sys.argv)
    cli.add_argument("-r", type=str, dest="REPLACE", default="", help="REPLACE", required=False)

    cli.add_argument("-ni", action="store_true", dest="no_interactive", help="no interaction")
    cli.add_argument("--gist", action="store_true", dest="show_gist", help="show some gist", required=False)

    parsed_args = cli.parse_args()
    if parsed_args.show_gist:
        cli.print_help()
        print(GIST)
        sys.exit(0)

    trigger(parsed_args)
