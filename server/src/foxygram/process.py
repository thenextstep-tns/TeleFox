"""Child processes must stay invisible: the packaged server has no console of its own."""
import subprocess

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
