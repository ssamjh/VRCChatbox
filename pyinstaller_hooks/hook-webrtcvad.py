# Override for pyinstaller-hooks-contrib's hook-webrtcvad.py.
#
# The contrib hook does `datas = copy_metadata('webrtcvad')`, but we install the
# package as `webrtcvad-wheels` (import name `webrtcvad`). That distribution name
# doesn't exist, so copy_metadata raises PackageNotFoundError and the build dies.
#
# webrtcvad is a single C-extension module that never reads its own metadata at
# runtime, so collecting nothing here is correct. Hooks in --additional-hooks-dir
# outrank contrib hooks and only the highest-priority hook per module runs, so
# this cleanly replaces the broken one.
datas = []
