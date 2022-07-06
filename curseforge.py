import asyncio
import json
import os
import sys
import zipfile
import shutil

import aiohttp
from aiohttp.client_exceptions import ContentTypeError


def gen_instance_cfg(file_path: str, mod_pack_name="", ):
    """
    生成 instance.cfg 文件
    :param file_path: 文件保存路径
    :param mod_pack_name: 模组包名称
    :return:
    """
    with open(file_path, "w") as f:
        f.write("InstanceType=OneSix\n")
        f.write(f"name={mod_pack_name}\n")  # 使用mod-pack名称 + mod-pack version 当做实例名


def gen_mmc_pack(file_path: str, minecraft_version: str, forge_version: str):
    """
    生成 mmc-pack.json 文件
    :param file_path: 文件保存路径
    :param minecraft_version: mc版本
    :param forge_version: forge版本
    :return:
    """
    temp_dict = {
        "components": [
            {"cachedName": "Minecraft", "uid": "net.minecraft", "version": minecraft_version},
            {"cachedName": "Forge", "uid": "net.minecraftforge", "version": forge_version}
        ],
        "formatVersion": 1
    }

    with open(file_path, "w") as file_mmc:
        json.dump(temp_dict, file_mmc, indent=4)


def parse_manifest(manifest_path: str):
    """
    解析整合包中的清单文件 确定需要下载的mod
    :param manifest_path: 清单文件路径
    :return:
    """
    pack_info = {}
    with open(manifest_path, "r") as manifest:
        manifest_json = json.load(manifest)
        pack_info["minecraft_version"] = manifest_json["minecraft"].get("version", "")
        pack_info["forge_version"] = manifest_json["minecraft"]["modLoaders"][0].get("id", "").split("-")[1]
        pack_info["mod_pack_name"] = manifest_json["name"]
        pack_info["mod_pack_version"] = manifest_json["version"]
        pack_info["mod_pack_author"] = manifest_json["author"]
        pack_info["mods"] = manifest_json["files"]

    return pack_info


async def download(manifest: list, save_path: str):
    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = [asyncio.create_task(download_mod(semaphore, session, project_info, save_path)) for project_info in
                 manifest]
        await asyncio.wait(tasks)


def unzip(zip_file_path: str, to_path: str):
    """
    解压一个zip文件到指定文件夹
    :param zip_file_path: zip文件全路径
    :param to_path: 解压到文件夹路径
    :return:
    """
    zip_file = zipfile.ZipFile(zip_file_path)  # 创建zipfile对象
    zip_file.extractall(path=to_path)  # 解压所有文件到指定文件夹


async def download_mod(sem, session, project_info: dict, save_path: str):
    async with sem:
        # base_url = "https://addons-ecs.forgesvc.net/api/v2/addon/"
        base_url = "https://api.curseforge.com"

        # 根据项目id和文件id取得mod文件的下载地址
        # url = f"{base_url}{project_info['projectID']}/file/{project_info['fileID']}"
        url = f"{base_url}/v1/mods/{project_info['projectID']}/files/{project_info['fileID']}"
        async with session.get(url=url) as response:
            try:
                temp_json = await response.json()
            except(ContentTypeError, TimeoutError, Exception):
                print(f"\t{url} 下载地址获取失败")
                return

            # 临时保存mod信息的字典
            temp_dict = {
                "id": temp_json["data"].get("id", ""),
                "filename": temp_json["data"].get("fileName", ""),
                "fileLength": temp_json["data"].get("fileLength", ""),
                "downloadUrl": temp_json["data"].get("downloadUrl", "")
            }

        if temp_dict["downloadUrl"] is None:  # 某些mod无法获得下载地址 这时候需要特殊处理
            get_mod_url = f"{base_url}/v1/mods/{project_info['projectID']}"
            async with session.get(url=get_mod_url) as get_mod:
                try:
                    json_to_dict = await get_mod.json()
                except(ContentTypeError, Exception):
                    print(f"\t 错误 {get_mod_url}")
                    return
                mod_website_url = json_to_dict["data"]["links"].get("websiteUrl", "")  # 获得mod的主页地址
                mod_download_page_url = f"{mod_website_url}/download/{project_info['fileID']}"  # 拼接mod下载页地址
                fail_list.append({"id": temp_dict.get("id"), "modDownloadPageUrl": mod_download_page_url, })
            return  # 由于没有下载地址 所以直接返回 不继续后面的下载动作

        # 开始下载mod
        async with session.get(url=temp_dict["downloadUrl"]) as mod_response:
            # 直接死循环 确保mod一定下载完成？
            while True:
                try:
                    mod_content = await mod_response.content.read()
                    break
                except(asyncio.TimeoutError, TimeoutError, Exception):
                    print("\t asyncio.TimeoutError")
                    pass

            # 写到文件
            with open(f"{save_path}/{temp_dict['filename']}", "wb") as save_file:
                save_file.write(mod_content)

        print(f"\t文件 {temp_dict['filename']} 下载完成")


async def main():
    # 初始化
    config_path = "./config.json"
    with open(config_path, "r") as f:
        config_json = json.load(f)
    multimc_path = config_json.get("multiMcPath", "")  # 从配置文件读取multimc的安装路径
    api_key = config_json.get("apiKey", "")  # 从配置文件读取apikey
    if not os.path.isdir(multimc_path):
        print("请在config.json中设置正确的multimc安装目录")
        quit()

    if api_key == "":
        print("请在config.json中设置正确的apikey")
        quit()

    headers["x-api-key"] = api_key

    multimc_instance_path = f"{multimc_path}/instances"  # multimc实例目录
    work_dir = multimc_instance_path  # 设置工作目录
    # 判断一下传进来的zip路径是否存在
    augments = sys.argv
    if len(augments) <= 1:
        print("请传递zip路径")
        quit()
    zip_file_path = augments[1]
    if not os.path.isfile(zip_file_path):
        print("请传递正确的zip文件路径")
        quit()

    print("解压压缩包...")
    # 设置一些必要的目录
    _, full_zip_file_name = os.path.split(zip_file_path)
    zip_file_name, _ = os.path.splitext(full_zip_file_name)  # 取得zip文件的文件名 用来作为解压文件夹的名称
    extract_folder_path = f"{work_dir}/{zip_file_name}"
    if os.path.isdir(extract_folder_path):  # 如果解压文件夹存在
        print(f"\t文件夹 {extract_folder_path} 存在，删除中...")
        shutil.rmtree(extract_folder_path)
    unzip(zip_file_path, extract_folder_path)

    print("构建工作目录...")
    manifest_path = f"{extract_folder_path}/manifest.json"
    minecraft_folder_path = f"{extract_folder_path}/minecraft"
    mods_folder_path = f"{minecraft_folder_path}/mods"
    instance_cfg_path = f"{extract_folder_path}/instance.cfg"  # instance.cfg 文件位置
    mmc_pack_json_path = f"{extract_folder_path}/mmc-pack.json"  # mmc-pack.json 文件位置
    try:
        os.rename(f"{extract_folder_path}/overrides", minecraft_folder_path)  # 将overrides文件夹改名为minecraft
    except FileExistsError:
        pass
    # 判断mod文件是否存在 如果不存在 则创建一个？
    if not os.path.exists(mods_folder_path):
        os.makedirs(mods_folder_path)

    print("解析mod清单...")
    if not os.path.isfile(manifest_path):
        print("mod清单文件不存在，请确认zip文件是否为curse forge整合包！")
        quit()
    pack_info = parse_manifest(manifest_path)

    print("下载mod...")
    await download(pack_info["mods"], mods_folder_path)
    print("构建MultiMc配置信息...")
    gen_instance_cfg(instance_cfg_path, f"{pack_info['mod_pack_name']} {pack_info['mod_pack_version']}")
    print("\t生成 instance.cfg 完毕")
    gen_mmc_pack(mmc_pack_json_path, pack_info["minecraft_version"], pack_info["forge_version"])
    print("\t生成 mmc-pack.json 完毕")

    if fail_list is not None:
        # 失败列表不为none
        print(f"下列mod无法自动下载，请手动下载后移动到 {mods_folder_path} 目录:")
        for item in fail_list:
            print(f"\t{item['modDownloadPageUrl']}")

    print("完成")


loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
semaphore = asyncio.Semaphore(5)
fail_list = []  # 保存下载失败mod

# 请求头
headers = {
    "user-agent": "Safari/537.36",
    'Accept': 'application/json',
    'x-api-key': "",
}

if __name__ == '__main__':
    loop.run_until_complete(main())
