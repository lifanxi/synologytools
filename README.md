# Tool scripts for Synology NAS

## arrange_photo.py

### 用途

可用于整理从手机上传到Photo Station的文件，逻辑如下：

- 按文件日期，以月为单位，把上传的文件组织（移动）到不同目录下
- 如果多次上传了相同的文件，最终只会保留一份，重复的文件会被抛弃
- 遇到以下情况时，文件会被留在原地不做处理，等待人工处理：
  - 文件中没有元信息
  - 文件名指示的日期与文件元信息中保存的日期不一致
  - 目标目录中存在同名文件，但文件与源目录中的不一致
- 在移动文件时，会同步更新Photo Station的索引。如果已经生成了缩略图，也会一并搬迁，避免重新生成
- 可选：在移动文件时，可以另行复制一份到一个临时目录中，这个临时目录可以通过Drive/DS cloud或Syncthing同步到Android手机（比如Google Pixel）上，由手机备份到Google Photos中

注意：只支持Photo Station，暂未考虑Moments中上传的照片，也未考虑Synology Photos的场景。但Photo Station共享给Moments的共享照片库，是可以正常工作的。

### 用法

调用```sh wait_and_arrange.sh <源目录名> <目标目录名>```。

其中，源目录名应为Photo Station中手机上传的目录，目标目录名为Photo Station中的一个目标目录。

### 示例

Photo Station的根目录为：```/volume1/photo```，里面有Bob和Alice的照片，各自在一个文件夹中。同时还有一个```Upload```目录，里面有Bob和Alice各自从手机上上传的照片。

```
/volume1/photo
           |-----Bob
           |-----Alice
           |-----Upload
                    |-----Bob
                    |-----Alice
```

有一天，Bob上传了一批照片：
```
/volume1/photo
           |-----Bob
           |-----Alice
           |-----Upload
                    |-----Bob
                        |---- IMG_20200412_102328.jpg
                        |---- IMG_20210112_122328.jpg
                        |---- IMG_20200512_132328.jpg
                    |-----Alice
```

执行命令：
```sh wait_and_arrange.sh /volume1/photo/Upload/Bob /volume1/photo/Bob```

得到的结果是：
```
/volume1/photo
           |-----Bob
                 |----2020
                     |----04
                        |---- IMG_20200412_102328.jpg
                     |----05
                        |---- IMG_20200512_132328.jpg
                 |----2021
                     |----01
                        |---- IMG_20210112_122328.jpg                        
           |-----Alice
           |-----Upload
                    |-----Bob
                    |-----Alice
```

为了方便起见，可以把上述的命令设置成一个定时任务，每天自动执行。如果Alice的照片也需要做类似的整理，可以再加一条类似的命令：

```sh wait_and_arrange.sh /volume1/photo/Upload/Alice /volume1/photo/Alice```

### 技术细节

- 为什么要调用```wait_and_arrange.sh```而不是直接用```arrange_photo.py```？
  ```wait_and_arrange.sh```会粗浅的检查一下是不是有索引任务正在执行，如果有未完成的索引任务，会等索引任务完成后，再做照片整理。避免在索引过程中移动了文件，造成索引混乱。

- 如何把文件额外备份到一个目录中给Google Photos上传？
  打开```arrange_photo.py```，找到```process```函数中的一大段注释，把它们打开就可以了。注意修改一下里面临时目录名，设置成为同步软件中设置的路径，注意权限。如果是EXT4文件系统，而不是BTRFS文件系统，还需要把```cp --reflink=always```改成```cp```。```--reflink=always```这个参数是给BTRFS文件系统用的，可以不真正复制一个文件，而只是COW，提高脚本的整体性能。

- 检查重复文件的逻辑是什么样？
  不会看文件的实际内容，只会对文件进行二进制比较，所以只能对重复文件去重，不能实现“相似”文件去重。为了提高文件比较效率，对于大于4MiB的文件，默认只会比较文件开头2MiB和尾部2MiB的内容。如果需要做精确全文件比较，请修改```calc_file_hash```函数。

- 什么情况下会出现文件名和元信息日期不一致的情况？
  如果你某天拍了一张照片，过几天又用手机自带的相册修改一下，这时手机会以当天的日期生成文件名保存你修改后的结果，但不会更新元信息。这样的照片如果上传到Moments或Google Photos后，排序会排到拍摄的那天去。这种情况下，建议修改文件元信息，让它能正确地排到修改的那天去。