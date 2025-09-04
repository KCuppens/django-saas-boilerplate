# Requirements Files

This directory contains environment-specific Python requirements files.

## Quick Reference

| File | Purpose | Installation |
|------|---------|-------------|
| `base.txt` | Core dependencies | Always included |
| `dev.txt` | Development setup | `pip install -r dev.txt` |
| `prod.txt` | Production setup | `pip install -r prod.txt` |
| `test.txt` | Testing setup | `pip install -r test.txt` |

## Usage

### Development
```bash
make install
# or
pip install -r requirements/dev.txt
```

### Production
```bash
make install-prod
# or
pip install -r requirements.txt
```

### Testing
```bash
make install-test
# or
pip install -r requirements/test.txt
```

For detailed information, see [docs/requirements.md](../docs/requirements.md).