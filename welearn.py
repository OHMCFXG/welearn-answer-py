import json
import os.path
import sys
import time
import zipfile
import requests
from bs4 import BeautifulSoup

##############################################
cid = 0  # 课程id，为0时启动关键词搜索模式
token = ''  # token, 留空时使用账号密码登录获取
phone = ''  # 手机号
passwd = ''  # 密码


##############################################


# 获取毫秒级时间戳
def get_time():
    return int(time.time() * 1000)


# 解压zip资源文件
def un_zip(dir_name, file_name):
    zip_file = zipfile.ZipFile(file_name)
    if os.path.isdir(dir_name):
        pass
    else:
        os.mkdir(dir_name)
    for f in zip_file.namelist():
        zip_file.extract(f, dir_name)


# 检查文件夹是否存在，不存在则创建
def check_create_dir(path):
    if os.path.isdir(path):
        pass
    else:
        os.mkdir(path)


# 搜索获取课程cid
def get_course_id(key):
    global cid
    url = "https://courseappserver.sflep.com/app/authservice.aspx"
    params = {
        'action': 'search_course_v3',
        'email': token,
        'key': key,
        't': get_time()
    }
    resp = requests.get(url, params=params).json()
    no = 1
    cids = []
    # error = True
    if resp["status"] == "0":
        for course in resp["list"]:
            cid = course["cid"]
            name = course["name"]
            cids.append(int(cid))
            print("%s.%s" % (no, name))
            no += 1
        while True:
            try:
                select = int(input("选择课程："))
                cid = cids[select - 1]
                break
            except ValueError:
                print("输入有误，请输入数字")
            except IndexError:
                print("输入有误，超出范围")

    return cid


# 获取课程活动html文件路径
def get_html_path(soursename, unitcode, scocode):
    if len(unitcode) == 1:
        unitcode = "0" + unitcode
    path = "./tmp/%s/unit_%s/main%s.html" % (soursename, unitcode, scocode)
    if os.path.exists(path):
        return path
    else:
        return ""


def find_answer(html_path):
    # 查找答案
    """
        题目类型 data-controltype（
        choice 单选题，
        multiChoice 多选题，
        filling 填空题，
        fillinglong 长填空题，
        writing 写作题，
        tf 是非题，
        switch 控制开关）
    """
    answers = ""

    f = open(html_path, "r", encoding='utf-8')
    soup = BeautifulSoup(f.read(), 'lxml')

    # 初筛出题目div
    questions = soup.findAll("div", attrs={
        "data-controltype": ["choice", "multiChoice", "filling", "fillinglong", "writing", "tf"]})

    for qu in questions:
        controltype = qu["data-controltype"]

        # 选择题，判断题
        if controltype == "choice":
            answer = qu.find("li", attrs={"data-solution": True}).text.strip().replace("\n", "")
            answers += "\t" + answer + "\n"
        # 客观填空题
        elif controltype == "filling":
            answer = qu.find(True, attrs={"data-solution": True})["data-solution"].strip()
            answers += "\t" + answer + "\n"
        # 主观题，翻译题
        elif controltype == "fillinglong":
            answer = qu.find(True, attrs={"data-solution": True})["data-solution"].strip()
            if answer == "Answers may vary.":
                answer = "主观题无参考答案"
            if answer == "1":
                answer = qu.find(True, attrs={"data-itemtype": "result"}).text
            answer = answer.replace("●", "\n要点●").replace("<br />", "")
            answers += "\t" + answer + "\n"
            if "●" in answers:
                answers += "\n"
        # 是非题
        elif controltype == "tf":
            answer = qu.find(True, attrs={"data-solution": True})["data-solution"].strip()
            answers += "\t" + answer + "\n"

    # print(answers)
    return answers


# 获取课程详情
def get_course_info(this_cid):
    url = "https://courseappserver.sflep.com/app/authservice.aspx"
    params = {
        'action': 'courseinfonotjoin',
        'email': token,
        'cid': this_cid,
        't': get_time()
    }
    resp = requests.get(url, params=params).json()
    course_name = resp["name"]
    zip_link = resp["txt_res"]
    folderInfo = json.loads(resp["folderJson"])

    # 创建临时文件夹，下载并解压资源文件
    check_create_dir("tmp")
    zip_file = requests.get(zip_link).content
    with open("./tmp/%s.zip" % course_name, "wb") as code:
        code.write(zip_file)
    un_zip("./tmp/%s" % course_name, "./tmp/%s.zip" % course_name)
    os.remove("./tmp/%s.zip" % course_name)

    # 输出课程信息
    courseInfo = []
    print(course_name)
    print("资源链接：%s" % zip_link)
    for unit in folderInfo["unit"]:
        unitname = unit["unitname"]
        print(unitname)
        for sco in unit["scolist"]:
            scoid = sco["scoid"]
            sconame = sco["sconame"]
            unit_code = str(scoid).split("-")[-2]
            sco_code = str(scoid).split("-")[-1]
            html_path = get_html_path(course_name, unit_code, sco_code)
            print("\t%s\t%s\t%s" % (scoid, sconame, html_path))
            courseInfo.append({
                "unitname": unitname,
                "sconame": sconame,
                "html_path": html_path
            })

    # 保存课程信息
    return course_name, courseInfo


def login():
    global token
    url = "https://courseappserver.sflep.com/app/authservice.aspx"
    data = {
        'action': 'ssologin2',
        'account': phone,
        'pwd': passwd
    }
    resp = requests.get(url, data=data).json()
    if resp["status"] == "-1":
        print(resp["msg"])
        sys.exit(-1)
    print("登录成功")
    token = resp["openid"]
    return token


def welearn():
    global cid, token
    if token == "":
        login()
    if cid == 0:
        search_key = input("请输入要搜索关键词：")
        cid = get_course_id(search_key)

    coursename, courseInfo = get_course_info(cid)

    # 创建课程答案文件夹
    check_create_dir("answers")
    check_create_dir("answers/%s" % coursename)

    # 创建答案txt
    with open("answers/%s/answer.txt" % coursename, "a+", encoding="utf-8") as f:
        for sco in courseInfo:
            if sco["html_path"]:
                scoanswer = find_answer(sco["html_path"])
                if scoanswer != "":
                    f.write("%s - %s\n%s\n\n" % (sco["unitname"], sco["sconame"], scoanswer))

    time.sleep(3)
    os.remove("./tmp")


if __name__ == '__main__':
    welearn()
