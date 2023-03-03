import os
import glob
import csv
import xml.etree.ElementTree as ET
from model import db_file
from typing import List
from app import app
from flask import jsonify, request, render_template, make_response, send_from_directory
import json
from .keypoint import get_point,get_dbtype_point,create_point,get_db_points
import zipfile
import xml.dom.minidom
from config import DIR
import time
import base64

@app.route('/getdirtree')
def get_dir_tree():
    resp = {'code':0, 'msg': '成功'}
    try:
        filePath = request.values.get('filePath')
        fileType = request.values.get('fileType')
        if fileType == '1':
            sql_str = ' and isDir = 1'
        elif fileType == '2':
            sql_str = ' and isDir = 0'
        else:
            sql_str = ''
        files = []
        sql = """select isDir, fileName, extendName,userFileId from userfile where filePath = '{}' {}""".format(filePath,sql_str)
        print(sql)
        result = db_file(sql)
        print(result)
        for res in result:
            item = {}
            item['isDir'] = res['isDir']
            item['filename'] = res['fileName']
            item['userFileId'] = res['userFileId']
            if res['extendName']:
                item['filename'] += '.' + res['extendName']
            files.append(item)
        resp['files'] = files
    except:
        resp['code'] = 1
        resp['msg'] = '失败'
    return json.dumps(resp)

# /zsh/label_data/images/,1008106,0,
def create_label(filePath, userFileId, person_id, person):
    sql = '''insert into ai_image set file_id={},path="{}",type="jpg",status=0'''.format(userFileId, filePath)
    db_file(sql)
    sql = '''select img_id from ai_image where file_id = {}'''.format(userFileId)
    res = db_file(sql)
    print(res)
    id = res[0]['img_id']
    print(id)
    create_point(person, id, person_id)

def get_label_tag(label_id):
    sql = '''select ai_tag.tag as tag from ai_label_tag, ai_tag where ai_label_tag.tag_id = ai_tag.tag_id and ai_label_tag.label_id = {}'''.format(label_id)
    print(sql)
    result = db_file(sql)
    if result:
        return result[0]['tag']
    else:
        return 'male'

def get_xml_file(zipFileCnt, person):
    filepath = DIR+'/yd_pose/test/test.zip'
    # filepath = '/home/yd/label_system/test.zip'
    f = zipfile.ZipFile(filepath,'w',zipfile.ZIP_STORED)
    paths = []
    names = []
    for item in person:
        #在内存中创建一个空的文档
        doc = xml.dom.minidom.Document() 
        #创建一个根节点Managers对象
        root = doc.createElement('annotation')
        #将根节点添加到文档对象中
        doc.appendChild(root) 
        nodeimage = doc.createElement('image')
        nodecategory = doc.createElement('category')
        nodesubcategory = doc.createElement('subcategory')
        nodekeypoints = doc.createElement('keypoints')
        nodeimage.appendChild(doc.createTextNode(item['image']))
        nodecategory.appendChild(doc.createTextNode('person'))
        label_id = item['label_id']
        tag = get_label_tag(label_id)
        nodesubcategory.appendChild(doc.createTextNode(tag))

        items = item['keypoints']
        for name in item['keypoints']:
            if items[name]['x'] == items[name]['y'] == items[name]['z'] == 0:
                continue
            nodekeypoint = doc.createElement('keypoint')
            #设置根节点的属性
            nodekeypoint.setAttribute('name', name)
            nodekeypoint.setAttribute('zorder', str(items[name]['zorder'])) 
            nodekeypoint.setAttribute('x', str(items[name]['x'])) 
            nodekeypoint.setAttribute('y', str(items[name]['y'])) 
            nodekeypoint.setAttribute('z', str(items[name]['z'])) 
            nodekeypoint.setAttribute('visible', str(items[name]['visible'])) 
            nodekeypoints.appendChild(nodekeypoint)

        root.appendChild(nodeimage)
        root.appendChild(nodecategory)
        root.appendChild(nodesubcategory)
        root.appendChild(nodekeypoints)
        path = DIR + '/yd_pose/test/' + str(item['image']) + '.xml'
        # path = '/home/yd/label_system/' + str(item['image']) + '.xml'
        fp = open(path, 'w')
        print(path)
        doc.writexml(fp, indent='\t', addindent='\t', newl='\n', encoding="utf-8")
        paths.append(path)
        names.append(str(item['image'])+'.xml')  
        fp.close()
        
    
    if not zipFileCnt:
        for i in range(len(paths)):
            print(paths[i])
            print(names[i])
            f.write(paths[i],'/' + names[i])
            os.remove(paths[i])
    else:
    ###打包成多个zip，再将所有zip压缩成一个总压缩包
        index = 0
        file_sum = len(paths)
        file_cnt = int(zipFileCnt)
        zip_cnt = (file_sum - 1) // file_cnt + 1
        zip_path = DIR+'/yd_pose/test/file_zip.zip'
        # zip_path = '/home/yd/label_system/file_zip.zip'
        for i in range(zip_cnt):
            file_zip = zipfile.ZipFile(zip_path,'w',zipfile.ZIP_STORED)
            for j in range(file_cnt):
                if index >= file_sum:
                    break
                print(paths[index])
                print(names[index])
                file_zip.write(paths[index],'/' + names[index])
                os.remove(paths[index])
                index += 1
            zip_name = '/{}.zip'.format(i + 1)
            file_zip.close()
            f.write(zip_path, zip_name)
            os.remove(zip_path)
    f.close()
    return [DIR+'/yd_pose/test/', 'test.zip']
    # return ['/home/yd/label_system/', 'test.zip']
    #os.remove(DIR+'/yd_pose/test/test.zip')
    # with open(DIR+'/yd_pose/test/test.zip','rb') as f1:
    #     base64_str = base64.b64encode(f1.read())
    # return base64_str
    
def get_image_wh(userFileId):
    sql = '''select imageHeight,imageWidth from userfile,image where userfile.userFileId={} and userfile.fileId=image.fileId'''.format(userFileId)
    res = db_file(sql)
    return (res[0]['imageHeight'], res[0]['imageWidth'])


def get_coco_file(userFileIds,person):
    # 生成coco文件
    db_type = 'push-up-2'
    if person:
        db_type = person[0]['filepath'][9:]
    userFileIds = userFileIds.split(',')
    save_path = DIR + '/annotations/'
    respath = save_path
    if not os.path.exists(save_path):
        os.mkdir(save_path)
    jsonname = db_type.split('/')[0]
    save_path = os.path.join(save_path, jsonname + '.json')
    resname = jsonname + '.json'
    joint_num = 17
    aid = 0
    # coco文件格式
    coco = {'images':[], 'categories':[], 'annotations':[]}
    # category格式
    category = {'supercategory':'person',
        'id':1,
        'name':'person',
        #"skeleton": [[16,14],[14,12],[17,15],[15,13],[12,13],[6,12],[7,13],[6,7],[6,8],[7,9],[8,10],[9,11],[2,3],[1,2],[1,3],[2,4],[3,5],[4,6],[5,7]],
        #"keypoints": ["nose","left_eye","right_eye","left_ear","right_ear","left_shoulder","right_shoulder","left_elbow","right_elbow",
        #    "left_wrist","right_wrist","left_hip","right_hip","left_knee","right_knee","left_ankle","right_ankle"]
        'keypoints':['body_head','neck','left_shoulder','right_shoulder','left_elbow','right_elbow','left_wrist','right_wrist','left_hip',
        'right_hip','left_knee','right_knee','left_ankle','right_ankle','nose','left_ear','left_eye','right_eye','right_ear'],
        'skeleton':[[0,1],[1,2],[1,3],[2,4],[3,5],[4,6],[5,7],[8,10],[9,11],[10,12],[11,13],[2,8],[3,9],[8,9],[1,14],[14,16],[16,15],[14,17],[17,18]]
        }
    for item in person:
        filename = str(item['image']) + '.jpg'
        filepath = db_type
        # 获取图片高和宽
        h, w = get_image_wh(userFileIds[aid])
        # images格式
        img_dic = {'id': aid, 'file_name': filepath+filename, 'coco_url':'http://images.cocodataset.org/'+filepath+filename, 'width': w, 'height': h}
        coco['images'].append(img_dic)
        # 获取关键点数据和数量
        kps = []
        numkeypoints = 0
        items = item['keypoints']
        bbox = [0,0,0,0]
        xmin = 0
        ymin = 0
        xmax = 0
        ymax = 0
        for keypoint in item['keypoints']:
            x = items[keypoint]['x']
            y = items[keypoint]['y']
            v = 2 if items[keypoint]['visible'] else 1
            if not (x == y == 0):
                numkeypoints += 1
                kps += [x,y,v]
                if v > 0:
                    if xmin > x or xmin == 0:
                        xmin = x
                    if xmax < x:
                        xmax = x
                    if ymin > y or ymin == 0:
                        ymin = y
                    if ymax < y:
                        ymax = y
        width = xmax - xmin + 1
        height = ymax - ymin + 1
        if width <= 0 or height <= 0:
            continue
        else:
            if width > height:
                if height/width < 0.15:
                    height = width * 0.15
            else:
                if width/height < 0.15:
                    width = height * 0.15
            width_ratio = 1.3 if width > height else 1.5
            height_ratio = 1.5 if width > height else 1.3
            bbox[0] = (xmin + xmax)/2. - width/2*width_ratio
            bbox[0] = max(bbox[0], 0)
            bbox[1] = (ymin + ymax)/2. - height/2*height_ratio
            bbox[1] = max(bbox[1], 0)
            bbox[2] = width*width_ratio
            if bbox[2] >= w - bbox[0]:
                bbox[2] = w - bbox[0] - 1
            bbox[3] = height*height_ratio
            if bbox[3] >= h - bbox[1]:
                bbox[3] = h - bbox[1] - 1

        # annotations格式
        person_dict = {'id':aid,'image_id':aid, 'category_id': 1, 'area': bbox[2]*bbox[3], 'bbox':bbox, 'iscrowd':0, 'keypoints': kps, 'numkeypoints': numkeypoints}
        coco['annotations'].append(person_dict)
        aid += 1
    category['keypoints'] = category['keypoints']
    category['skeleton'] = category['skeleton']
    coco['categories'] = [category] 
    with open(save_path, 'w') as f:
        json.dump(coco, f)
    return [respath, resname]        

def get_custom_file(cocopath):
    output_name = '{}_custom.json'.format(cocopath[1][:-5])
    output_file = DIR + '/annotations/' + output_name
    input_file = DIR + '/annotations/' + cocopath[1]
    order_map = {0: 13, 1: 11, 2: 9, 3: 8, 4: 10, 5: 12, 6: 1, 7: 0, 8: 7, 9: 5, 10: 3, 11: 2, 12: 4, 13: 6}

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    input_anno = data['annotations']
    input_img = data['images']
    print('annotations:', len(input_anno), 'images:', len(input_img))
    dict_img = {}
    for img in input_img:
        dict_img[img['id']] = img['file_name']
    res = []
    for i in input_anno:
        image = dict_img[i['image_id']]
        ## 训练时会重新计算visibility，此处结果可不管
        #visibility = [1 if j == 2 else 0 for j in i['keypoints'][2::3]]
        #bbox = [i['bbox'][:2], i['bbox'][2:]]

        points = []
        for x, y, v in zip(i['keypoints'][0::3], i['keypoints'][1::3], i['keypoints'][2::3]):
            if v != 0:
                points.append([x, y])
            else:
                points.append([-1, -1])
        print(points)
        #points = sorted([i for i in zip(order_map.values(), points)], key=lambda k: k[0])
        #points = [i[1] for i in points]

        # print({'image': image, 'points': points, 'visibility': visibility, 'bbox': bbox})
        res.append({'image': image, 'points': points})
    print('输出数量：', len(res))

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(res, f)
    return output_name

@app.route('/label_download', methods=['GET','POST'])
def label_download():
    # 标注文件下载
    userFileIds = request.values.get('userFileIds')
    fileType = request.values.get('fileType')
    zipFileCnt = request.values.get('zipFileCnt', '')
    resp = {}
    resp['code'] = 1
    resp['msg'] = '未知原因'
    
    # -------------------------------------
    # 没有选定图片，获取不到图片的userFilelds
    if not userFileIds:
        resp['code'] = 1
        resp['msg'] = '没有选择图片'
        return resp
    
    if fileType not in ['coco','xml','custom']:
        resp['code'] = 1
        resp['msg'] = '文件类型错误'
    person = get_db_points(userFileIds)

    # ------------------------------------
    # 没有获取到数据
    # 不会报500服务器异常错误
    if not person:
        resp['code'] = 1
        resp['msg'] = '文件没有标注数据'
        return resp
    
    idList = userFileIds.split(',')
    if len(person) != len(idList):
        resp['code'] = 1
        resp['msg'] = '部分文件未存在标注文件'
        # ---------------------------------
        return resp
    
    if fileType == 'xml':
        filepath = get_xml_file(zipFileCnt, person)
        respath = filepath[0]
        resname = filepath[1]
    elif fileType == 'coco':
        filepath = get_coco_file(userFileIds, person)
        respath = filepath[0]
        resname = filepath[1]
    elif fileType == 'custom':
        cocopath = get_coco_file(userFileIds, person)
        resname = get_custom_file(cocopath)
        respath = cocopath[0]
    #file = make_response(send_from_directory(respath, resname, as_attachment=True))
    #resp['file'] = file
    try:
        return make_response(send_from_directory(respath, resname, as_attachment=True))
    except:        
        return json.dumps(resp)

import logging
import requests
# @app.route('/filetransfer/uploadfile')
# def upload():
#     # return render_template('commit.html')
#     url = 'http://192.168.100.98:1080/papi/filetransfer/uploadfile'
#     response = requests.post(url=url)
#     logging.debug("response.request.headers:{}".format(response.request.headers)) # 请求头
#     # response_post = requests.post(url=post_url,data=data)
#     logging.debug("response.status_code:{}".format(response.status_code)) # 状态码
#     logging.debug("response.request:{}".format(response.request)) # 请求方法
#     logging.debug("response.headers:{}".format(response.headers)) # 响应头
#     logging.debug("response.text:{}".format(response.text)) # 响应内容
#     return 'zsh'

    
@app.route('/papi/filetransfer/uploadfile', methods=['GET','POST'])
def uploadlabelfile():
    # xml文件上传接口
    
    from config import DIR, tflite_path
    

    # flask代理请求到java api接口，上传完python获取数据做处理
    try:
        # 获取要上传文件的路径和名字
        filePath = request.args.get('filePath')
        filename = request.args.get('filename')
        headers = request.headers
        # url = request.url
        url = 'http://192.168.100.98:1080/papi/filetransfer/uploadfile'
        response = requests.post(url=url)
        # api_url = url[:26]+'/api'+url[26:]
        # logging.debug("get_url:{}".format(api_url))
        # logging.debug("headers:{}".format(headers))
        # logging.debug("url:{}".format(url))
        # api_res = request.url
        # logging.debug("api_res:{}".format(api_res))
        # response = requests.get(url=api_url,headers=headers)

        # 上传指定文件,格式字符串加入文件名字和路径
        # requests.get（）发送http get请求，构造一个向服务器请求资源的url对象
        # 返回的是一个包含服务器资源的Response对象。包含从服务器返回的所有的相关资源

        logging.debug("response.request.headers:{}".format(response.request.headers)) # 请求头
        # response_post = requests.post(url=post_url,data=data)
        logging.debug("response.status_code:{}".format(response.status_code)) # 状态码
        logging.debug("response.request:{}".format(response.request)) # 请求方法
        logging.debug("response.headers:{}".format(response.headers)) # 响应头
        logging.debug("response.text:{}".format(response.text)) # 响应内容

#         response.close
#         # 服务器储存文件的绝对路径
#         file = DIR+filePath+filename
#         f = open(file,'w')
#         # logging.debug("f:{}".format(f))
#         logging.debug("f.read():{}".format(f.read()))
        
        return "z"
        resp = {}
        resp['code'] = 1
        # 没有找到文件，上传失败
        if not file:
            resp['msg'] = '上传失败'
            return resp
 
        person = get_point(file)
        logging.debug("person:{}".format(person))

        keypoint = get_dbtype_point(person)
        keypoint = ','.join(keypoint)
        try:
            # filename, person_id = filename.split('_')

            # 去除后缀
            filename_split = filename.split('.')
            filename = filename_split[0]+'.'+filename_split[1]
            person_id = 0
            # logging.debug("filename:{}".format(filename))
        except:
            resp['msg'] = '文件名错误'
            return resp
        sql = '''select userFileId from userfile where filePath="{}" and fileName="{}"'''.format(filePath, filename)
        result = db_file(sql)
        # logging.debug("result:{}".format(result))

        if result:
            userFileId = result[0]['userFileId'] # 1008101
            logging.debug("userFileId:{}".format(userFileId))

            sql = '''select img_id from ai_image where file_id={}'''.format(userFileId)
            result = db_file(sql)
            logging.debug("result:{}".format(result))

            if not result:
                create_label(filePath, userFileId, person_id, person)
                resp['code'] = 0
                resp['msg'] = '标注文件已生成'
                return resp
            img_id = result[0]['img_id'] # 266609
        else:
            resp['msg'] = '文件不存在'
            return resp
        if not keypoint:
            resp['msg'] = '失败'
            return resp
        sql = 'update ai_label_skeleton set status=0,{} where img_id={}'.format(keypoint,img_id)
        print(sql)
        db_file(sql)
        sql = 'select label_id from ai_label_skeleton where img_id={}'.format(img_id)
        result = db_file(sql)
        if result:
            label_id = result[0]['label_id']
            sql = '''select * from ai_tag,ai_label_tag where ai_label_tag.label_id={} and ai_label_tag.tag_id=ai_tag.tag_id
                and tag_id.tag={}'''.format(label_id, person['subcategory'])
        resp['code'] = 0
        resp['msg'] = '标注文件已更改'
        return resp

    except Exception as e:
        logging.error("执行函数报错", exc_info=True)
        return '执行函数报错'