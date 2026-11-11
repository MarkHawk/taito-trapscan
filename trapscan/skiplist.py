"""Set-name prefixes for hardware outside the scope of these searches (fruit machines, video poker,
console-based arcade systems, handhelds). Used by --skip-nonarcade in sigsearch.

Prefix matching is by name only, so it's a time saver, not an exact filter: check the counts it prints.
"""
NONARCADE = (
    # UK/EU fruit machines (AWPs): Barcrest MPU1-5, JPM, Maygay, BFM Scorpion, Astra
    'm1', 'm3', 'm4', 'm5', 'j2', 'j5', 'j6', 'j7', 'ep_', 'sc1', 'sc2', 'sc4', 'sc5', 'as_',
    # video poker
    'pex',
    # console-based arcade systems (1986+) and handheld dumps
    'pc_', 'mt_', 'gnw_',
)


def skipped(filename, prefixes):
    name = filename.lower().rsplit('/', 1)[-1]
    return any(name.startswith(p) for p in prefixes)


def parse(args):
    """Prefixes from --skip-nonarcade and --skip a,b,c."""
    out = list(NONARCADE) if getattr(args, 'skip_nonarcade', False) else []
    if getattr(args, 'skip', None):
        out += [p.strip().lower() for p in args.skip.split(',') if p.strip()]
    return tuple(out)


def add_args(ap):
    ap.add_argument('--skip-nonarcade', action='store_true',
                    help='skip fruit machines, video poker, PlayChoice/Mega-Tech and Game & Watch sets '
                         '(by name prefix: ' + ' '.join(NONARCADE) + ')')
    ap.add_argument('--skip', metavar='PREFIXES', help='also skip sets whose names start with these, comma-separated')
