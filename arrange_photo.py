#! /usr/bin/python2.7
import re
import sys
import os
import hashlib
import exifread
import shutil
import subprocess
import datetime

VIDEO_FILE_EXT = ['MP4', 'MOV', '3GP']


def calc_file_hash(filename, size):
    ''' 
    Calculate the file hash.
    In order to have better performance, if the file is larger than 4MiB,
    only the first and last 2MiB content of the file will take into consideration
    '''
    sample_size = 2 * 1024 * 1024
    if size <= sample_size * 2:
        return hashlib.md5(open(filename, 'rb').read()).hexdigest()
    else:
        f = open(filename, 'rb')
        md51 = hashlib.md5(f.read(sample_size)).hexdigest()
        f.seek(size - sample_size)
        return hashlib.md5(md51 + f.read(sample_size)).hexdigest()


def get_date_from_file_name(filename):
    '''
    Use regex to guess the date of the photo from file name
    '''
    f = os.path.basename(filename)
    m = re.match(
        r'[IMGVDnShotcre]{3,10}_([0-9]{4})([0-9]{2})([0-9]{2})_[0-9]*', f)
    if m != None:
        return (m.group(1), m.group(2), m.group(3))
    return ("0", "0", "0")


def get_time_from_file_name(filename):
    '''
    Use regex to guess the time of the photo from file name
    '''
    f = os.path.basename(filename)
    m = re.match(
        r'[IMGVDnShot]{3,6}_[0-9]{4}[0-9]{2}[0-9]{2}_([0-9]{2})([0-9]{2})([0-9]{2})*', f)
    if m != None:
        return (m.group(1), m.group(2), m.group(3))
    return ("0", "0", "0")


def get_date_from_meta(filename):
    '''
    Get the date of the photo/video from EXIF information or file meta
    '''
    # If this is a video file, use ffmpeg to read the meta data
    if filename[-3:].upper() in VIDEO_FILE_EXT:
        try:
            output = subprocess.check_output(
                'ffmpeg -i %s 2>&1|grep creation_time | head -n1 |cut -f 2- -d ":"' % filename, shell=True).strip()
            date = (datetime.datetime.strptime(output, "%Y-%m-%d %H:%M:%S") +
                    (datetime.datetime.now() - datetime.datetime.utcnow())).strftime("%Y %m %d").split(" ")
            return (date[0], date[1], date[2])
        except Exception as e:
            print(e)
            return ("0", "0", "0")

    # Otherwise, this is a photo, use various ways to get the date
    try:
        with open(filename, 'rb') as img:
            # Try to use exifread library to read the EXIF
            tags = exifread.process_file(img, stop_tag="Date", details=False)
            if len(tags) == 0:
                # Fall back to use exiv2 to read the EXIF, if exifread failed to parse EXIF data
                try:
                    output = subprocess.check_output(
                        "exiv2 %s |grep 'Image timestamp' | cut -f 2- -d ':'" % filename, shell=True).strip()
                    date = datetime.datetime.strptime(
                        output, "%Y:%m:%d %H:%M:%S").strftime("%Y %m %d").split(" ")
                    print("use exiv2 info")
                    return (date[0], date[1], date[2])
                except Exception as e:
                    print(e)
                    return ("0", "0", "0")
            if 'EXIF DateTimeOriginal' in tags:
                m = re.match(
                    r'([0-9]{4}):([0-9]{2}):([0-9]{2}) [0-9]{2}:[0-9]{2}:[0-9]{2}', str(tags['EXIF DateTimeOriginal']))
                if m != None:
                    return (m.group(1), m.group(2), m.group(3))
            if 'GPS GPSDate' in tags:
                m = re.match(
                    r'([0-9]{4})-([0-9]{2})-([0-9]{2})', str(tags['GPS GPSDate']))
                if m != None:
                    return (m.group(1), m.group(2), m.group(3))
            img.close()
    except:
        print("Error: %s" % filename)
    return ("0", "0", "0")


def get_date_from_file(filename):
    '''
    Use various ways to get date from file
    '''
    y, m, _ = get_date_from_file_name(filename)
    if y == "0" or m == "0":
        y, m, _ = get_date_from_meta(filename)
    return (y, m)


def check_conflict(old, new):
    # If the destination file does not exist, it's safe
    if not os.path.exists(new):
        return False
    # If the desitnation is a directory, it does not meet our expection
    if os.path.isdir(new):
        return True
    # If the destination file exists, and its size is different, it's not safe
    stat_old = os.lstat(old)
    stat_new = os.lstat(new)
    if stat_old.st_size != stat_new.st_size:
        return True
    # If the destination file is not the same with source file, we should not overwrite it
    filehash_old = calc_file_hash(old, stat_old.st_size)
    filehash_new = calc_file_hash(new, stat_new.st_size)
    if filehash_old != filehash_new:
        return True
    # Otherwise, the two files are identical, it's safe to overwrite it
    return False


def create_dir(path, ignore_index):
    '''
    Create a new directory, and add it to Photo Station index
    '''
    parent_dir = os.path.dirname(path)
    if not os.path.exists(parent_dir):
        create_dir(parent_dir, ignore_index)
    if not os.path.exists(path):
        os.mkdir(path)
        if not ignore_index:
            print("synoindex -A '%s'" % path)
            os.system("synoindex -A '%s'" % path)


def do_move(old, new, ignore_index):
    '''
    Move the file (with its thumbnail to destination location
    and update the Photo Station index if necessary
    '''
    # Check output path
    if not os.path.isdir(os.path.dirname(new)):
        create_dir(os.path.dirname(new), ignore_index)
    # Move file first
    shutil.move(old, new)
    print(old + "==>" + new)
    # Then, move the thumbnail
    old_thumb = os.path.join(os.path.dirname(
        old), "@eaDir", os.path.basename(old))
    new_thumb = os.path.join(os.path.dirname(new), "@eaDir")
    if os.path.isdir(old_thumb):
        if os.path.exists(os.path.join(new_thumb, os.path.basename(new))):
            shutil.rmtree(os.path.join(new_thumb, os.path.basename(new)))
        shutil.move(old_thumb, new_thumb)
        print (old_thumb + "-->" + new_thumb)
        # Update index
        if not ignore_index:
            print ("synoindex -n '%s' '%s'" % (new, old))
            os.system("synoindex -n '%s' '%s'" % (new, old))
    else:
        # Add the file to index
        if not ignore_index:
            print ("synoindex -a '%s'" % (new))
            os.system("synoindex -a '%s'" % (new))


def check_valid(filename):
    '''
    Check if the file is valid to be indexed.
    '''
    (y1, m1, d1) = get_date_from_file_name(filename)
    print(y1, m1, d1)
    (y2, m2, d2) = get_date_from_meta(filename)
    print(y2, m2, d2)
    if y2 == "0":
        if y1 == "0":
            # Cannot get date information from file name or file meta, invalid
            print("no date info")
            return False
        else:
            # There is no date information in file meta, this should be fixed
            print("need to update exif")
            ext = filename.split(".")[-1].upper()
            (h1, mm1, s1) = get_time_from_file_name(filename)
            if ext in VIDEO_FILE_EXT:
                # TODO: calculate correct timestamp with time zone
                print('ffmpeg -i %s  -codec copy -metadata creation_time="xxxx-xx-xx xx:xx:xx" output.mp4; cp output.mp4 %s' %
                      (filename, filename))
            else:
                print('exiv2 -M"set Exif.Photo.DateTimeOriginal %s:%s:%s %s:%s:%s"  %s' %
                      (y1, m1, d1, h1, mm1, s1, filename))
            return False
    elif y1 != "0":
        # Date information get from file name does not consist with file meta, invalid
        if y1 != y2 or m1 != m2 or d1 != d2:
            print("exif and file name inconsist")
            return False
        return True


def process(dirname, photo_root, ignore_index):
    if dirname == photo_root:
        print("src and dst directory can not be the same")
        return
    for root, dirs, files in os.walk(dirname):
        if '@eaDir' in root:
            continue
        print (root, dirs, files)
        for f in files:
            full_file_name = os.path.join(root, f)
            # Invalid file will be skipped until they get fixed manually
            # If there is incosistency with the file, it may cause incorrect ordering in the photo library,
            # especially when uploaded to Google Photos or re-indexed in moments.
            if not check_valid(full_file_name):
                print("Found file with inconsistency %s" % full_file_name)
                continue

            (y, m) = get_date_from_file(full_file_name)
            if y != "0":
                # Generate the destination path for the file
                new_path = os.path.join(photo_root, y, m, f)
                if not check_conflict(full_file_name, new_path):
                    # If you want the new files to be write to a temporary folder,
                    # and sync that folder to Android device (eg. Google Pixel) for uploading to Google Photos,
                    # you many uncomment the following lines.
                    # If you are not using BTRFS, remove the '--reflink=always' option from the cp command

                    # ext = ""
                    # # Rename the .MOV file, otherwise Google Photos may not upload the file
                    # if full_file_name.endswith("MOV"):
                    #    ext = ".MP4"
                    # os.system("cp --reflink=always '%s' /volume1/syncthing/%s%s" % (full_file_name, os.path.basename(full_file_name), ext))

                    do_move(full_file_name, new_path, ignore_index)
                else:
                    print("Found conflict file %s %s" %
                          (full_file_name, new_path))


if __name__ == '__main__':
    ignore_index = False
    if len(sys.argv) == 4 and sys.argv[3] == '--ignore-index':
        ignore_index = True
    if len(sys.argv) != 3 and len(sys.argv) != 4:
        print("Usage: ./arrange <src dir> <dst dir> [--ignore-index]")
        print("Without --ignore-index, <src dir> and <dst dir> MUST be the PhotoStation photo directory or a sub directory inside it")
        sys.exit(-1)
    process(os.path.abspath(sys.argv[1]),
            os.path.abspath(sys.argv[2]), ignore_index)
