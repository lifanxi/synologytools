#! /usr/bin/python2.7
import re
import sys
import os
import glob
import md5
import hashlib
import exifread
import shutil

def calc_file_hash(filename, size):
    sample_size = 2 * 1024 * 1024
    if size <= sample_size:
        return hashlib.md5(open(filename, 'rb').read()).hexdigest()
    else:
        f = open(filename, 'rb')
        md51 = hashlib.md5(f.read(sample_size)).hexdigest()
        f.seek(size - sample_size)
        return hashlib.md5(md51 + f.read(sample_size)).hexdigest()

def get_date_from_file(filename):
    # Method 1: File Name
    f = os.path.basename(filename)
    m = re.match(r'[IMGVID]{3}_([0-9]{4})([0-9]{2})[0-9]{2}_[0-9]*', f)
    if m != None:
        return (m.group(1),m.group(2))
    # Method 2: EXIF
    img = open(filename, 'rb')
    tags = exifread.process_file(img, stop_tag='DateTimeOriginal')
    if 'EXIF DateTimeOriginal' in tags:
        m = re.match(r'([0-9]{4}):([0-9]{2}):[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}', str(tags['EXIF DateTimeOriginal']))
        if m != None:
            return (m.group(1),m.group(2))
    return ("0","0")

def check_conflict(old, new):
    if not os.path.exists(new):
        return False
    if os.path.isdir(new):
        return True
    stat_old = os.lstat(old)
    stat_new = os.lstat(new)
    if stat_old.st_size != stat_new.st_size:
        return True
    filehash_old = calc_file_hash(old, stat_old.st_size)
    filehash_new = calc_file_hash(new, stat_new.st_size)
    if filehash_old != filehash_new:
        return True
    return False

def create_dir(path, ignore_index):
    parent_dir = os.path.dirname(path)
    if not os.path.exists(parent_dir):
        create_dir(parent_dir, ignore_index)
    if not os.path.exists(path):
        os.mkdir(path)
        if not ignore_index:
            print("synoindex -A '%s'" % path)
            os.system("synoindex -A '%s'" % path)

def do_move(old, new, ignore_index):
    # Check output path
    if not os.path.isdir(os.path.dirname(new)):
        create_dir(os.path.dirname(new), ignore_index)
    # Move file first
    shutil.move(old, new)
    print(old + "==>" +new)
    # Move the thumb
    old_thumb = os.path.join(os.path.dirname(old), "@eaDir", os.path.basename(old))
    new_thumb = os.path.join(os.path.dirname(new), "@eaDir")
    if os.path.isdir(old_thumb):
        if os.path.exists(os.path.join(new_thumb, os.path.basename(new))):
            shutil.rmtree(os.path.join(new_thumb, os.path.basename(new)))
        shutil.move(old_thumb, new_thumb);
        print (old_thumb + "-->" + new_thumb);
        # Update index
        if not ignore_index:
            print ("synoindex -n '%s' '%s'" % (new, old))
            os.system("synoindex -n '%s' '%s'" % (new, old))
    else:
        if not ignore_index:
            print ("synoindex -a '%s'" % (new))
            os.system("synoindex -a '%s'" % (new))
    
def process(dirname, photo_root, ignore_index):
    if dirname == photo_root:
        print "src and dst directory can not be the same"
        return
    for root, dirs, files in os.walk(dirname):
        if '@eaDir' in root:
            continue
        postfix = os.path.basename(root)
        print (root,dirs,files)
        for f in files:
            full_file_name = os.path.join(root,f)
            (y,m) = get_date_from_file(full_file_name)
            if y != "0":
                new_path = os.path.join(photo_root, y, m, f)
                if not check_conflict(full_file_name, new_path):
                    do_move(full_file_name, new_path, ignore_index)
                else:
                    print("Found conflict file %s %s" % (full_file_name, new_path))

if __name__ == '__main__':
    ignore_index = False
    if len(sys.argv) == 4 and sys.argv[3] == '--ignore-index':
        ignore_index = True
    if len(sys.argv) != 3 and len(sys.argv) != 4:
        print("Usage: ./arrange <src dir> <dst dir> [--ignore-index]")
        print("Without --ignore-index, <src dir> and <dst dir> MUST be the PhotoStation photo directory or a sub directory inside it")
        sys.exit(-1)
    process(os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2]), ignore_index)
    
