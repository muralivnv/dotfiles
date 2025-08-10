BEGIN {
    cS = "\033[1;32m";
    cU = "\033[1;31m";
    cQ = "\033[1;34m";
    c0 = "\033[0m";
}
substr($0,1,2) == "??" {
    print cQ "? " c0 substr($0,4);
    next;
}
{
    staged   = substr($0,1,1);
    unstaged = substr($0,2,1);
    file     = substr($0,4);
    if (staged != " ") print cS "S " c0 file;
    if (unstaged != " ") print cU "U " c0 file;
}

