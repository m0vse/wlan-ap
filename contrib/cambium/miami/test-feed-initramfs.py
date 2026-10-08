#!/usr/bin/env python3
"""Exercise the actual patched make assignment and initramfs recipe."""
from pathlib import Path
import re, subprocess, tempfile
repo = Path(__file__).resolve().parents[3]
patch = repo/'patches-25.12/0162-kernel-defaults-resolve-feed-initramfs-inputs.patch'
with tempfile.TemporaryDirectory(prefix='miami-feed-initramfs-') as directory:
    work = Path(directory)
    # An assembled shared recipe is provided explicitly on the build host.
    import sys
    source = Path(sys.argv[1]).read_text()
    assignment = re.search(r'INITRAMFS_EXTRA_FILES .*?\n\n',source,re.S).group()
    generic = work/'feed-generic'
    main = work/'target/linux/generic/image'
    main.mkdir(parents=True); generic.mkdir()
    main_file = main/'initramfs-base-files.txt'
    main_file.write_text('nodes')
    def resolve(override=''):
        (work/'Makefile').write_text('TOPDIR := '+str(work)+'\nGENERIC_PLATFORM_DIR := '+str(generic)+'\n'+override+assignment+'all:\n\t@echo $(INITRAMFS_EXTRA_FILES)\n')
        return subprocess.check_output(['make','-s','-f',str(work/'Makefile')],text=True).strip()
    assert resolve() == str(main_file)
    (generic/'image').mkdir()
    own_file = generic/'image/initramfs-base-files.txt'
    own_file.write_text('own nodes')
    assert resolve() == str(own_file)
    assert resolve('INITRAMFS_EXTRA_FILES := explicit.cpio\n') == 'explicit.cpio'
    start = source.index('define Kernel/CompileImage/Initramfs\n')
    end = source.index('\nendef',start)+len('\nendef')
    recipe = source[start:end]
    target = work/'root';target.mkdir()
    kernel = work/'kernel';(kernel/'usr').mkdir(parents=True)
    inputs = work/'inputs';inputs.mkdir();(inputs/'init').write_text('init')
    marker = work/'stale-image-copied'
    # Mock only compiler/copy boundaries: actual recipe must abort before copy.
    variables = f"""TARGET_DIR := {target}
LINUX_DIR := {kernel}
GENERIC_OTHER_FILES_DIR := {inputs}
CP := cp
KERNEL_MAKE := false
locked = $(1)
Kernel/Configure/Initramfs = :
Kernel/CopyImage = touch {marker}
"""
    (work/'Makefile').write_text(variables+recipe+'\nall:\n\t$(call Kernel/CompileImage/Initramfs)\n')
    result = subprocess.run(['make','-s','-f',str(work/'Makefile')],capture_output=True,text=True)
    assert result.returncode != 0 and not marker.exists(), result.stdout+result.stderr
print('PASS: main-tree fallback, feed preference, explicit override and actual recipe failure propagation')
