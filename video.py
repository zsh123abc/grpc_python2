import cv2 
import os 
from config import DIR
from models import db_file
from app import app
from flask import request
from .database import insert_file,insert_folder
import logging

def get_frame_name(outPutDir, videoName, times):
    #命名视频帧
    n = len(videoName)
    videoName = '0'*(3-n) + videoName
    n = len(str(times))
    times = '0'*(4-n) + times
    filename = outPutDir + videoName + times + '.jpg'
    return [filename,videoName+times]

def get_frame(videoPath, videoName, outPutDir, fileurl, frame_cnt):
    #要提取视频的文件名，隐藏后缀 
    sourceFileName=videoName
    #在这里把后缀接上 
    video_path = DIR + videoPath + sourceFileName+'.mp4' 
    print(video_path)
    times=0
    #输出图片到当前目录vedio文件夹下 
    if not os.path.exists(DIR+outPutDir):     
        #如果文件目录不存在则创建目录     
        os.makedirs(DIR+outPutDir)
        insert_folder(outPutDir[:-18], 'label_data')
        insert_folder(outPutDir[:-7],outPutDir[-7:-1])

    n = 1
    #视频路径正确，cv2读取视频帧率一直为0
    camera = cv2.VideoCapture(fileurl)
    fps = camera.get(cv2.CAP_PROP_FPS)
    logging.debug("fps:{}".format(fps))
    
    #提取视频的频率，每50帧提取一个 
    if frame_cnt:
        frameFrequency=int(frame_cnt)
    else:
        frameFrequency=int(fps)
    print(frameFrequency)
    print(frame_cnt)
    while True:     
        times+=1     
        res, image = camera.read()
        
        print(res)
        if not res:         
            print('not res , not image')
            break
        if times%frameFrequency==0:    
            res = get_frame_name(DIR+outPutDir, videoName, str(n))
            n += 1
            filename = res[0]
            name = res[1]
            print(filename)
            print(name)
            cv2.imwrite(filename, image)      
            sql = '''select * from userfile where filePath="{}" and fileName="{}"'''.format(outPutDir, name)
            if not db_file(sql): 
                insert_file(outPutDir, name,'jpg')
    print('图片提取结束')
    camera.release()

def get_video_info(userFileIds):
    #获取视频文件信息
    sql = '''select fileName,filePath,extendName,fileId from userfile where userFileId in ({})'''.format(userFileIds)
    print(sql)
    result = db_file(sql)
    videopath = []
    videolist = []
    videoextend = []
    videofileid = []
    for res in result:
        videopath.append(res['filePath']) 
        videolist.append(res['fileName'])
        videoextend.append(res['extendName'].lower())
        videofileid.append(res['fileId'])
    print(videopath)
    print(videoextend)
    videopath = set(videopath)
    videoextend = set(videoextend)
    if len(videopath) != 1:
        return 0
    elif len(videoextend) != 1:
        return 1
    res = [list(videopath)[0], list(videoextend)[0], videolist, videofileid]
    return res

@app.route('/get_video_frame', methods=['POST'])
def get_video_frame():
    resp = {}
    resp['code'] = 0
    resp['msg'] = 'ok'
    userFileIds = request.form['userFileIds']
    frame_cnt = ''
    if 'frame_cnt' in request.form:
        frame_cnt = request.form['frame_cnt']

    # -----------------------------------------
    if not userFileIds:
        resp['code'] = 1
        resp['msg'] = '没有获取到视频userFileIds'
        return resp

    print(userFileIds)
    video_info = get_video_info(userFileIds)
    # logging.debug('video_info:{}'.format(video_info))

    if video_info == 0:
        resp['code'] = 1
        resp['msg'] = 'Video Path Error'
        return resp
    elif video_info == 1:
        resp['code'] = 1
        resp['msg'] = 'Video Type Error'
        return resp

    videopath = video_info[0]
    videolist = video_info[2]
    videofileid = video_info[3]
    print(videopath)
    print(videolist)
    if videopath[-8:] != '/videos/':
        resp['code'] = 1
        resp['msg'] = 'Video Path Error'
        return resp
    outPutDir=videopath[:-7]+'label_data/images/'
    logging.debug('outPutDir:{}'.format(outPutDir))

    n = len(videolist)
    for i in range(n):
        video = videolist[i]
        fileid = videofileid[i]
        sql = '''select fileUrl from file where fileId={}'''.format(fileid)
        fileurl = db_file(sql)[0]['fileUrl']
        fileurl = DIR + '/' + fileurl
        logging.debug("{},{},{},{},{}".format(videopath, video, outPutDir, fileurl, frame_cnt))
        get_frame(videopath, video, outPutDir, fileurl, frame_cnt)
    return resp

