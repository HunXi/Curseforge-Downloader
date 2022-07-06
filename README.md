# 使用方法
使用之前请安装`python3`并安装`aiohttp`包

随后编辑`config.json`文件，设置`multiMcPath`的值为`multimc`或`polymc`启动器安装路径

设置`apiKey`值为你申请到的key [点我申请key](https://console.curseforge.com/?#/)

然后去curseforge下载想玩的整合包（仅支持forge整合）

之后打开命令行输入:
```shell
python .\curseforge.py xxxx.zip
```

完成之后打开`multimc`或`polymc`启动器即可看到新增的实例

# 其他的东西
某些mod无法通过api获得下载地址，所以某些整合包的某些mod无法自动下载，不过无需担心，在程序运行完成后，会提示若干mod无法下载，这时只需点击给出的url就可以直接下载