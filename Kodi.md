
## Kodi插件自定义修改及使用教程

影视大全(改)插件基于小明的影视大全修改而来，添加了部分爬虫及Alist网盘支持，除Alist爬虫外两插件的爬虫文件相互兼容。

### 自定义修改

##### 1.插件目录结构

Kodi插件采用ZIP方式压缩封装。plugin.video.ysdqg.zip解压缩plugin.video.ysdqg为插件源码目录。

plugin.video.ysdqg/spider_XXX.py：爬虫文件

plugin.video.ysdqg/spider_config.py：插件爬虫配置文件

plugin.video.ysdqg/resources/settings.xml:插件设置文件

plugin.video.ysdqg/resources/language/resource.language.zh_cn(resource.language.en_us)/strings.po：插件语言文件

plugin.video.ysdqg/resources/images：爬虫图标目录

##### 2.添加/删除爬虫

1.添加/删除目录下spider_XXX.py文件

![image](https://raw.githubusercontent.com/lm317379829/PyramidStore/pyramid/img/sc.jpg)
2. 添加/删除spider_config.py文件中对应内容：from 爬虫文件名 import 爬虫名 

                                          爬虫名.__name__: 爬虫名(),

![image](https://raw.githubusercontent.com/lm317379829/PyramidStore/pyramid/img/set.jpg)
3. 添加/删除settings.xml文件中对应内容：<setting label="320XX" type="bool" id="爬虫开关" default="true"/>，爬虫开关信息在爬虫文件def hide(self)中。

![image](https://raw.githubusercontent.com/lm317379829/PyramidStore/pyramid/img/sp.jpg)
4. 添加/删除删除strings.po文件中对应内容：msgctxt "#320XX" 
                                        msgid "爬虫开关"
                                        msgstr "爬虫中文名"

5.添加/删除images目录中的爬虫图标。

##### 3.使用教程

通过如下配置自定义爬虫相关内容，可设置Token、Alist网盘地址、直播分类、77源哎呦疼忙解析地址。参考模板见YSDQ.json，下载后自行修改，上传至支持外链的网盘或github后填入Token/外链设置。文件需严格遵守json文件格式。

https://raw.githubusercontent.com/lm317379829/PyramidStore/pyramid/YSDQ.json

插件设置→阿里云盘设置→Token/外链设置

![image](https://raw.githubusercontent.com/lm317379829/PyramidStore/pyramid/img/jx.jpg)

![image](https://raw.githubusercontent.com/lm317379829/PyramidStore/pyramid/img/json.jpg)