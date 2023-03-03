import os
import glob
import csv
import xml.etree.ElementTree as ET
from model import db_file 
from app import app
from flask import jsonify, request
import json
from PIL import Image
from config import DIR, tflite_path
from . import database as db
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import time
import skimage.io as io
import asyncio
import cv2
import logging

#from ai_robot import convert
#from .ai_robot import getPersonKeypoints
#from .ai_robot import PoseEstimator
#from ai_robot import time_synchronized
#from ai_robot import padding_img

#@app.route('/point/<path:localSystemFilePath>', methods=['GET'])
def get_point(xmlpath):
    # xmlpath为上传的文件或文件路径，返回骨骼点
    tree = ET.parse(xmlpath)
    root = tree.getroot()
    person = {}
    for obj in root:
        if obj.tag == "image":
            person["image"] = obj.text
        if obj.tag == "subcategory":
            person["subcategory"] = obj.text
        if obj.tag == "keypoints":
            person["keypoints"] = {}
            for child in obj:
                name = child.attrib["name"]
                person["keypoints"][name] = child.attrib
    return person

def get_dbtype_point(person):
    person_keys = ['B_Head','Neck','L_Shoulder','R_Shoulder','L_Elbow','R_Elbow','L_Wrist','R_Wrist','L_Hip',
        'R_Hip','L_Knee','R_Knee','L_Ankle','R_Ankle','Nose','L_Ear','L_Eye','R_Eye','R_Ear']
    keypoint = []
    for key in person['keypoints']:
        idx = person_keys.index(key) + 1
        for item in ['x','y','z','zorder','visible']:
            s = '%s%d=%s'%(item, idx, person['keypoints'][key][item])
            keypoint.append(s)
    return keypoint

#@app.route('/createpoint/<path:localSystemFilePath>', methods=['GET'])
def create_point(person, img_id, person_id):
    keypoint = get_dbtype_point(person)
    person_id = int(person_id)
    img_id = int(img_id)
    status = 0
    sql = '''insert into ai_label_skeleton set person_id=%d,img_id=%d,status=%d,%s'''%(person_id, img_id, status, ','.join(keypoint))
    print(sql)
    db_file(sql)
    #sql = '''select max(label_id) as id from ai_label_skeleton'''
    sql = '''select label_id from ai_label_skeleton where img_id={}'''.format(img_id)
    label_id = db_file(sql)[0]['label_id']
    try:
        tag = person['subcategory']
        sql = '''select tag_id from ai_tag where tag="{}"'''.format(tag)
        res = db_file(sql)
        if not res:
            sql = '''insert into ai_tag set tag="{}"'''.format(tag)
            db_file(sql)
            sql = '''select tag_id from ai_tag where tag="{}"'''.format(tag)
            res = db_file(sql)
        tag_id = res[0]['tag_id']
        sql = '''insert into ai_label_tag set tag_id={},label_id={}'''.format(tag_id,label_id)
        db_file(sql)
    except:
        pass

def get_db_point(userFileId):
    sql = '''select * from ai_image as img,ai_label_skeleton as label where img.file_id = {} and img.img_id = label.img_id'''.format(userFileId)
    result = db_file(sql)
    if not result:
        return None
    result = result[0]
    person_keys = ['B_Head','Neck','L_Shoulder','R_Shoulder','L_Elbow','R_Elbow','L_Wrist','R_Wrist','L_Hip',
        'R_Hip','L_Knee','R_Knee','L_Ankle','R_Ankle','Nose','L_Ear','L_Eye','R_Eye','R_Ear']
    data = {}
    keypoints = {}
    for i in range(19):
        keypoints[person_keys[i]] = {}
        keypoints[person_keys[i]]['x'] = result['x'+str(i+1)]
        keypoints[person_keys[i]]['y'] = result['y'+str(i+1)]
        keypoints[person_keys[i]]['z'] = result['z'+str(i+1)]
        keypoints[person_keys[i]]['zorder'] = result['zorder'+str(i+1)]
        keypoints[person_keys[i]]['visible'] = result['visible'+str(i+1)]
    data['person_id'] = result['person_id']
    data['keypoints'] = keypoints
    return data

def get_db_points(userFileIds):
    sql = '''select * from ai_image as img,ai_label_skeleton as label where img.file_id in ({}) and img.img_id = label.img_id'''.format(userFileIds)
    result = db_file(sql)
    if not result:
        return None


    person_keys = ['B_Head','Neck','L_Shoulder','R_Shoulder','L_Elbow','R_Elbow','L_Wrist','R_Wrist','L_Hip',
        'R_Hip','L_Knee','R_Knee','L_Ankle','R_Ankle','Nose','L_Ear','L_Eye','R_Eye','R_Ear']
    resp = []
    for res in result:
        sql = '''select fileName,filePath from userfile where userFileId={}'''.format(res['file_id'])
        img = db_file(sql)[0]['fileName']
        filepath = db_file(sql)[0]['filePath']
        data = {}
        keypoints = {}
        for i in range(19):
            keypoints[person_keys[i]] = {}
            keypoints[person_keys[i]]['x'] = res['x'+str(i+1)]
            keypoints[person_keys[i]]['y'] = res['y'+str(i+1)]
            keypoints[person_keys[i]]['z'] = res['z'+str(i+1)]
            keypoints[person_keys[i]]['zorder'] = res['zorder'+str(i+1)]
            keypoints[person_keys[i]]['visible'] = res['visible'+str(i+1)]
        data['person_id'] = res['person_id']
        data['image'] = img
        data['keypoints'] = keypoints
        data['filepath'] = filepath
        data['label_id'] = res['label_id']
        resp.append(data)
    return resp

def get_label_status(userFileId):
    sql = '''select label.status as status from ai_label_skeleton as label,
        ai_image as image where image.file_id={} and image.img_id = label.img_id limit 1'''.format(userFileId)
    result = db_file(sql)
    resp = {}
    if result:
        status = result[0]['status']
        resp['status'] = status
        resp['code'] = 0
        resp['msg'] = '成功'
    else:
        resp['code'] = 1
        resp['msg'] = '没有标注数据'
    return resp

@app.route('/get_labelimage', methods = ['GET'])
def get_labelimage():
    # time1 = time.time()
    isMin = request.values.get('isMin')
    userFileId = request.values.get('userFileId')
    if not db_file('''select * from ai_image where file_id = {} limit 1'''.format(userFileId)):
        data = {}
        data['code'] = 1
        data['msg'] = '标注文件不存在'
        return json.dumps(data)
    filepath = db.get_image_path(userFileId)
    filelist = filepath.split('/')
    #os.chdir(DIR)
    imgpath = DIR + filepath
    # linewidth = 5
    # size = 12
    # if isMin == 'true':
    #     plt.rcParams['figure.figsize'] = (1.5, 1.5)
    #     linewidth = 2
    #     size = 3
    # else:
    #     plt.rcParams['figure.figsize'] = (8.0, 10.0)
    # plt.axis('off')
    data = {}
    data['code'] = 1
    data['msg'] = '打开文件失败'
    #data = get_point(xmlpath)
    #I = io.imread(imgpath)
    #I = plt.imread(imgpath)
    # while(0):
    #     try:
    #         plt.imshow(I)
    #         break
    #     except:
    #         time.sleep(0.5)
    # plt.imshow(I)
    #plt.show()
    if len(filelist)<3 or filelist[-2]!='images' or filelist[-3]!='label_data' or isMin not in ('true','false'):
        data = {}
        #image = base64.encodebytes(sio.getvalue()).decode()
        #data['image'] = image
        data['status'] = 0
        data['code'] = 1
        data['msg'] = '文件非图片或请求参数错误'
        return data
    data = get_db_point(userFileId)
    logging.debug("data:{}".format(data))
    if not data:
        #sio = BytesIO()
        #plt.savefig(sio, format='png')
        #plt.clf()
        #plt.close()
        data = {}
        #image = base64.encodebytes(sio.getvalue()).decode()
        #data['image'] = image
        #data['status'] = 0
        data['code'] = 1
        data['msg'] = "没有标注文件"
        return data
    
    keys = ['B_Head','Neck','L_Shoulder','R_Shoulder','L_Elbow','R_Elbow','L_Wrist','R_Wrist','L_Hip',
        'R_Hip','L_Knee','R_Knee','L_Ankle','R_Ankle','Nose','L_Ear','L_Eye','R_Eye','R_Ear']
    point_x = []
    point_y = []
    point_v = []
    lines = [[0,1],[1,2],[1,3],[2,4],[3,5],[4,6],[5,7],[8,10],[9,11],[10,12],[11,13],[2,8],[3,9],[8,9]]
    for key in keys:
        if key in data['keypoints']:
            if key in ['Nose','L_Ear','L_Eye','R_Eye','R_Ear']:
                continue
            point_x.append(float(data['keypoints'][key]['x']))
            point_y.append(float(data['keypoints'][key]['y']))
            point_v.append(int(data['keypoints'][key]['visible']))
    # for line in lines:
    #     point1,point2 = line
    #     x1 = point_x[point1]
    #     x2 = point_x[point2]
    #     y1 = point_y[point1]
    #     y2 = point_y[point2]
    #     plt.plot([x1,x2],[y1,y2], linewidth=linewidth, color='black')
    
    # plt.plot(point_x,point_y,'.',markersize=size)
    #plt.show()
    
    '''
    xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    cv2处理图片
    '''
    img = cv2.imread(imgpath)
    logging.debug("img:{}".format(img))
    
    for line in lines:
        point1,point2 = line
        x1 = point_x[point1]
        x2 = point_x[point2]
        y1 = point_y[point1]
        y2 = point_y[point2]
        start_point = (int(x1), int(y1))
        end_point = (int(x2), int(y2))
        if start_point == (0,0) or end_point == (0,0):
            continue
        if point_v[point1] and point_v[point2]:
            cv2.line(img, start_point, end_point, (0,255,0), 5)
    for i in range(14):
        if point_v[i]:
            cv2.circle(img,(int(point_x[i]),int(point_y[i])),3,(255,0,0),3)
    if isMin == 'true':
        # 等比例裁剪成150*150
        ori_h, ori_w, _ = img.shape
        if ori_h<=ori_w:
            h = 150
            w = ori_w*150//ori_h
            img = cv2.resize(img, (w, h))
            t = (w-150)//2
            img = img[0:150, t:w-t].copy()
        else:
            h = ori_h*150//ori_w
            w = 150
            img = cv2.resize(img, (w, h))
            t = (h-150)//2
            img = img[t:h-t,0:150].copy()
        #img = cv2.resize(img, (150,150))
        image = cv2.imencode('.jpeg',img)[1]
        src = 'data:image/jpeg;base64,'

    else:
        #img = cv2.resize(img, (450,450))
        image = cv2.imencode('.jpg',img)[1]
        src = 'data:image/jpg;base64,'
    image = str(base64.b64encode(image))[2:-1]

    image = src + image
    resp = get_label_status(userFileId)
    resp['image'] = image
    return resp
    '''
    xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    '''


    # sio = BytesIO()
    # if isMin == 'true':
    #     plt.savefig(sio, format='jpeg')
    #     src = 'data:image/jpeg;base64,'
    # else:
    #     plt.savefig(sio, format='png')
    #     src = 'data:image/png;base64,'
    # plt.clf()
    # plt.close() 
    # resp = {}  
    
    # try:     
    #     image = base64.encodebytes(sio.getvalue()).decode()
    #     #print(1)
    #     #print(image)
        
    #     sql = '''select label.status as status from ai_label_skeleton as label,
    #     ai_image as image where image.file_id={} and image.img_id = label.img_id limit 1'''.format(userFileId)
    #     result = db_file(sql)
    #     time2 = time.time()
    #     print(time2-time1)
    #     #print(result)
    #     status = result[0]['status']
    #     resp['image'] = '<img src="%s"/>' % (src + image)
    #     resp['status'] = status
    #     resp['code'] = 0
    #     resp['msg'] = '成功'
    #     #print(resp)
    # except Exception as e:
    #     resp['code'] = 1
    #     resp['msg'] = str(e)
    #     #print(e)
    # return resp['image']
    # return resp

def xmlsave():
    n = 0
    sql = "select filePath, fileName from userfile where extendName='xml' and filePath like '%/label_data/info/'"
    result = db_file(sql)
    for res in result:
        path = res['filePath'][:-5] + 'images/'
        name = res['fileName'][:-2]
        sql = "select userFileId,extendName from userfile where filePath='{}' and fileName='{}'".format(path,name)
        ans = db_file(sql)
        if not ans:
            continue
        userFileId = ans[0]['userFileId']
        extendName = ans[0]['extendName']
        try:
            sql = """insert into ai_image set file_id={},path='{}',type='{}',status=0""".format(userFileId, path, extendName)
            db_file(sql)
            sql = """select max(img_id) as id from ai_image"""
            img_id = db_file(sql)[0]['id']
            filePath = DIR + res['filePath'] + res['fileName'] + '.xml'
            person_id = res['fileName'][-1]
            create_point(filePath, img_id, person_id)
        except:
            pass
        n += 1
        if n > 1000:
            time.sleep(2)
            n = 0

@app.route('/get_label_info')
def get_label_info():
    img_id = request.values.get('img_id')
    resp = {}
    resp['code'] = 0
    data = get_db_point(img_id)
    if not data:
        resp['code'] = 0
    resp['data'] = data
    return json.dumps(resp)


@app.route('/file/set_label_status', methods=['POST'])
def set_label_status():
    status = request.form['status']
    files = request.form['userFileIds']
    status = int(status)
    resp = {}
    resp['code'] = 0
    resp['msg'] = '成功'
    if status not in (0,1,2,3):
        resp['code'] = 1
        resp['msg'] = 'status is not in (0,1,2,3)'
        return json.dumps(resp)
    try:
        sql = '''select img_id from ai_image where file_id in ({})'''.format(files)
        result = db_file(sql)
        
        # -----------------------------------
        idList = files.split(',')
        if len(result)!=len(idList):
            resp['code'] = 1
            resp['msg'] = '部分文件无标注数据'
            return json.dumps(resp)

        img_ids = []
        for res in result:
            img_ids.append(str(res['img_id']))
        img_ids = ','.join(img_ids)
        print(img_ids)
        sql = '''update ai_label_skeleton set status={} where img_id in ({})'''.format(status, img_ids)
        print(sql)
        db_file(sql)
        
    except:
        resp['code'] = 1
        resp['msg'] = 'files error'
    return json.dumps(resp)


@app.route('/skeleton_calculate', methods=['GET', 'POST'])
def skeleton_calculate():
    img_dir = request.values.get('img_dir')
    userFileIds = request.values.get('userFileIds')
    # logging.debug('img_dir:{}'.format(img_dir))

    import sys
    sys.path.append('../')
    from file import client  

    # 调用其他容器里的骨骼预测方法    
    # respones = client.skeleton_calculate(img_dir, userFileIds) 
    # respones
    # logging.debug('response:{}'.format(respones))
    # return respones

    """
    没有调用grpc！！！！！！！！！！！！！
    """

    try:
        resp = {}
        img_path = DIR+img_dir
        # logging.debug('img_path:{}'.format(img_path))
        os_path = os.path.isdir(DIR+img_dir)
        # logging.debug('os_path:{}'.format(os_path))
        if not userFileIds or not img_dir:
            resp['code'] = 1
            resp['msg'] = '输入参数错误'
            return resp

        
        from .ai_robot import getPersonKeypoints
        from .ai_robot import PoseEstimator

        # convert(img_dir, userFileIds)
        
        
        
    except Exception as e:
        logging.error("执行函数报错", exc_info=True)
        return '执行函数报错'

        
        onnx_path=tflite_path 
        # logging.debug('service_res:{}'.format(res))
        person_keys = ['B_Head','Neck','L_Shoulder','R_Shoulder','L_Elbow','R_Elbow','L_Wrist','R_Wrist','L_Hip',
            'R_Hip','L_Knee','R_Knee','L_Ankle','R_Ankle','Nose','L_Ear','L_Eye','R_Eye','R_Ear']
        # csv_output_rows = []

        p = PoseEstimator(model_path=onnx_path)
        userfile_str = ''
        if userFileIds:
            userfile_str = 'and userFileId in ({})'.format(userFileIds)
        #print(sql)
        sql = '''select userFileId,fileName from userfile where filePath="{}" and extendName="jpg" {}'''.format(img_dir, userfile_str)
        result = db_file(sql)

        # -----------------------------
        if not result:
            resp['code'] = 1
            resp['msg'] = '文件格式错误'
            return resp

        # -----------------------------
        idList = userFileIds.split(',')
        if len(result)!=len(idList):
            resp['code'] = 1
            resp['msg'] = '部分文件格式错误'
            return resp

        for res in result:
            print(res)
            name = res['fileName'] + '.jpg'
            userFileId = res['userFileId']
            sql = '''select * from ai_image where file_id={}'''.format(userFileId)
            flag = True
            if not db_file(sql):
                sql = '''insert into ai_image set file_id={}, path="{}",type="jpg",status=0'''.format(userFileId, img_dir)
                db_file(sql)
                sql = '''select img_id from ai_image where file_id={}'''.format(userFileId)
                flag = False
            img_id = db_file(sql)[0]['img_id']
            print(flag)
            file = DIR+img_dir+name
            print(file)
            img = cv2.imread(file)
            if img is None:
                continue
            predict = p.predict(img)
            person = getPersonKeypoints(name, predict[0])
            #print(person)
            data = person["image"]
            kps = []
            for keypoint in person['keypoints']:
                idx = person_keys.index(keypoint) + 1
                for k in person['keypoints'][keypoint]:
                    str_point = '%s%s=%s' % (k, idx, person['keypoints'][keypoint][k])
                    #print(str_point)
                    kps.append(str_point)
            keypoints = ','.join(kps)
            #print(keypoints)
            sql = '''select label_id from ai_label_skeleton where img_id={}'''.format(img_id)
            label_result = db_file(sql)
            if label_result:
                sql = '''update ai_label_skeleton set person_id=0,status=0,{} where img_id={}'''.format(keypoints, img_id)
                db_file(sql)
            else:
                sql = '''insert into ai_label_skeleton set person_id=0,status=0,img_id={},{}'''.format(img_id, keypoints)
                db_file(sql)
                sql = '''select label_id from ai_label_skeleton where img_id={}'''.format(img_id)
                label_id = db_file(sql)[0]['label_id']
                sql = '''insert into ai_label_tag set tag_id = 1,label_id={}'''.format(label_id)
                db_file(sql)
    

    resp['code'] = 0
    resp['msg'] = '成功'
    return resp