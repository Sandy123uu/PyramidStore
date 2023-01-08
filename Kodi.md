
## Kodi插件自定义修改及使用教程

影视大全(改)插件基于小明的影视大全修改而来，添加Alist网盘支持与豆瓣聚搜，兼容部分小明大佬插件爬虫。

### 自定义修改

##### 1.插件目录结构

Kodi插件采用ZIP方式压缩封装。plugin.video.ysdqg.zip解压缩plugin.video.ysdqg为插件源码目录。

plugin.video.ysdqg/spider_XXX.py：爬虫文件

plugin.video.ysdqg/spider_config.py：插件爬虫配置文件

plugin.video.ysdqg/resources/settings.xml：插件设置文件

plugin.video.ysdqg/resources/language/resource.language.zh_cn(resource.language.en_us)/strings.po：插件语言文件

plugin.video.ysdqg/resources/images：爬虫图标目录

##### 2.添加/删除爬虫

1.添加/删除目录下spider_XXX.py文件

![image](https://raw.githubusercontent.com/lm317379829/PyramidStore/pyramid/img/sc.jpg)

2. 添加/删除spider_config.py文件中对应内容：
                                          
                                          from 爬虫文件名 import 爬虫名 

                                          爬虫名.__name__: 爬虫名(),

![image](https://raw.githubusercontent.com/lm317379829/PyramidStore/pyramid/img/set.jpg)

3. 添加/删除settings.xml文件中对应内容：

                                       <setting label="320XX" type="bool" id="爬虫开关" default="true"/>

爬虫开关信息在爬虫文件def hide(self)中。

![image](https://raw.githubusercontent.com/lm317379829/PyramidStore/pyramid/img/sp.jpg)

4. 添加/删除删除strings.po文件中对应内容：
                                        
                                        msgctxt "#320XX" 
                                        msgid "爬虫开关"
                                        msgstr "爬虫中文名"

5.添加/删除images目录中的爬虫图标。

##### 3.使用教程

通过如下配置自定义爬虫相关内容，可通过json文件配置Alist网盘地址、直播分类信息、哎呦疼忙解析接口、Ali-token(外链或token)、B站cookies(外链或cookies)、B站视频分类、找资源所需用户名密码等。其中，YSDQ下thlimit为单个搜索最大线程数，硬件配置不够的可以调小；speedLimit为直播源最低速度，低于speedLimit的直播源将被舍弃，支持单位M、K(大小写均可)，1M=1024K；searchList为启用的搜索站点：qq=七七、ik=爱看、bw=被窝、ld=零度、bb=哔哩哔哩番剧、ps=盘搜、ys=易搜、zzy=找资源、xzt=小纸条。

https://raw.githubusercontent.com/lm317379829/PyramidStore/pyramid/YSDQ.json

插件设置→阿里云盘设置→Token/外链设置

![image](https://raw.githubusercontent.com/lm317379829/PyramidStore/pyramid/img/jx.jpg)

![image](https://raw.githubusercontent.com/lm317379829/PyramidStore/pyramid/img/json.jpg)

![image](https://raw.githubusercontent.com/lm317379829/PyramidStore/pyramid/img/json2.jpg)

![image](https://raw.githubusercontent.com/lm317379829/PyramidStore/pyramid/img/json3.png)

![image](https://raw.githubusercontent.com/lm317379829/PyramidStore/pyramid/img/搜索相关.jpg)

![image](https://raw.githubusercontent.com/lm317379829/PyramidStore/pyramid/img/json4.jpg)

