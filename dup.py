#!env python
import os
import sys
import hashlib
import sqlite3


def calc_file_hash(filename, size):
    '''
    Calculate the file hash.
    In order to have better performance, if the file is larger than 20MiB,
    only the first and last 10MiB content of the file will take into consideration
    '''
    sample_size = 10 * 1024 * 1024
    if size <= sample_size * 2:
        return hashlib.md5(open(filename, 'rb').read()).hexdigest()
    else:
        f = open(filename, 'rb')
        md51 = hashlib.md5(f.read(sample_size)).hexdigest()
        f.seek(size - sample_size)
        return hashlib.md5((md51 + str(f.read(sample_size))).encode("utf-8")).hexdigest()


def create_db(name):
    db = sqlite3.connect(name)
    db.text_factory = str
    db.execute('''CREATE TABLE files (id INTEGER PRIMARY KEY, size INTEGER, name TEXT, hash TEXT, dir TEXT, dup INTEGER DEFAULT 0)''')
    db.commit()
    return db


def close_db(db):
    db.close()


def insert_file(db, dir, name, size):
    db.execute('''INSERT INTO files(size, name, hash, dir) VALUES(?, ?, ?, ?)''',
               (size, name, '', dir))


def run(dirnames, method):
    try:
        os.unlink("./dup.db")
    except:
        pass
    db = create_db('./dup.db')
    # First we find all files and store file sizes to DB
    for dirname in dirnames:
        for root, _, files in os.walk(dirname):
            if root.endswith("/.git") or root.find("/.git/") != -1 or root.endswith("/.svn") or root.find("/.svn/") != -1:
                continue
            if root.endswith("/@eaDir") or root.find("/@eaDir/") != -1:
                continue
            print("Processing " + root + "...")
            for f in files:
                try:
                    full_file_name = os.path.join(root, f)
                    filedir = os.path.dirname(full_file_name)
                    filename = os.path.basename(full_file_name)
                    stat = os.lstat(full_file_name)
                    if stat.st_size == 0:
                        print("Skip empty:\t%s" % (full_file_name))
                    elif os.path.islink(full_file_name):
                        print("Skip soft link:\t%s" % (full_file_name))
                    else:
                        insert_file(db, filedir, filename, stat.st_size)
                except Exception as e:
                    print("Exception: " + str(e))

    # We find out all files with the same size and calculate their hashes
    print("Calculating file hashes ...")
    for row in db.execute('''SELECT id, dir, name, size FROM files WHERE size IN (SELECT size FROM files GROUP BY size HAVING COUNT(size) > 1)'''):
        db.execute('''UPDATE files SET hash = ? WHERE id = ?''', (str(
            calc_file_hash(os.path.join(row[1], row[2]), row[3])), row[0]))

    # Mark duplicate files
    print("Marking duplicates ...")
    for row in db.execute('''SELECT id FROM files WHERE hash IN (SELECT hash FROM files WHERE hash != '' GROUP BY hash HAVING COUNT(hash) > 1)'''):
        db.execute('''UPDATE files SET dup = 1 WHERE id = ?''', (str(row[0]),))

    db.commit()

    # Now make reflinks for the duplicated files
    print("Making reflinks...")
    with open("./dup.sh", "w") as output:
        output.write("#! /bin/bash\nset -e\n")
        base_file = ''
        last_hash = ''
        for row in db.execute('''SELECT dir, name, hash FROM files WHERE dup = 1 ORDER BY hash'''):
            f = os.path.join(row[0], row[1])
            escaped_file_name = str(f).replace("'", "'\\''")
            if (base_file == '' and last_hash == '') or (base_file != '' and last_hash != row[2]):
                base_file = f
                last_hash = row[2]
                if method == 'check':
                    output.write('''echo '%s' \n''' % escaped_file_name)
                continue
            if method == 'delete':
                output.write('''echo 'Deleteing... %s' \n''' %
                             escaped_file_name)
                output.write('''rm -f '%s' \n''' % escaped_file_name)
            elif method == 'softlink':
                output.write('''echo 'Soft linking %s ==> %s' \n''' % (
                    str(base_file).replace("'", "'\\''"), escaped_file_name))
                output.write('''ln -sf '%s' '%s'\n''' %
                             (str(base_file).replace("'", "'\\''"), escaped_file_name))
            elif method == 'hardlink':
                output.write('''echo 'Hard linking %s ==> %s' \n''' % (
                    str(base_file).replace("'", "'\\''"), escaped_file_name))
                output.write('''ln -f '%s' '%s'\n''' %
                             (str(base_file).replace("'", "'\\''"), escaped_file_name))
            elif method == 'reflink':
                output.write('''echo 'Reflinking %s ==> %s' \n''' % (
                    str(base_file).replace("'", "'\\''"), escaped_file_name))
                output.write('''cp --reflink=always '%s' '%s' \n''' %
                             (str(base_file).replace("'", "'\\''"), escaped_file_name))
            else:
                output.write('''echo '%s' \n''' % escaped_file_name)

    close_db(db)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python ./dup.py <dir1> [dir2 ...] <method>")
        print("method can be check, delete, softlink, hardlink, reflink(BTRFS only)")
        sys.exit(-1)
    method = sys.argv[-1].lower()
    dirnames = [os.path.abspath(d) for d in sys.argv[1:-1]]
    run(dirnames, method)
