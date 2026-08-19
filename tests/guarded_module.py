from astrid.core.pack.entrypoint import guard_canonical_entrypoint
guard_canonical_entrypoint('demo.capability')
def main(argv=None):
    return argv if argv is not None else 0
