from __future__ import division

from models import *
from utils.utils import *
from utils.datasets import *

import os
import sys
import time
import datetime
import argparse
import cv2

from PIL import Image

import torch
from torch.utils.data import DataLoader
from torchvision import datasets
from torch.autograd import Variable

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.ticker import NullLocator

from mqtt_engine import MQTTEngine

def changeRGB2BGR(img):
    r = img[:, :, 0].copy()
    g = img[:, :, 1].copy()
    b = img[:, :, 2].copy()

    # RGB > BGR
    img[:, :, 0] = b
    img[:, :, 1] = g
    img[:, :, 2] = r

    return img

def changeBGR2RGB(img):
    b = img[:, :, 0].copy()
    g = img[:, :, 1].copy()
    r = img[:, :, 2].copy()

    img[:, :, 0] = r
    img[:, :, 1] = g
    img[:, :, 2] = b

    return img


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image_folder", type=str, default="data/test/", help="path to dataset")
    parser.add_argument("--video_file", type=str, default="0", help="path to dataset")
    parser.add_argument("--model_def", type=str, default="config/yolov3-tiny.cfg", help="path to model definition file")
    # parser.add_argument("--weights_path", type=str, default="weights/yolov3-tiny.weights", help="path to weights file")
    parser.add_argument("--weights_path", type=str, default="checkpoints_cafe7/tiny1_4000.pth", help="path to weights file")
    parser.add_argument("--class_path", type=str, default="data/cafe2/classes.names", help="path to class label file")
    parser.add_argument("--conf_thres", type=float, default=0.8, help="object confidence threshold")
    parser.add_argument("--nms_thres", type=float, default=0.4, help="iou thresshold for non-maximum suppression")
    parser.add_argument("--batch_size", type=int, default=1, help="size of the batches")
    parser.add_argument("--n_cpu", type=int, default=0, help="number of cpu threads to use during batch generation")
    parser.add_argument("--img_size", type=int, default=416, help="size of each image dimension")
    parser.add_argument("--checkpoint_model", type=str, help="path to checkpoint model")
    opt = parser.parse_args()
    print(opt)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    os.makedirs("output", exist_ok=True)

    # Set up model
    model = Darknet(opt.model_def, img_size=opt.img_size).to(device)

    if opt.weights_path.endswith(".weights"):
        # Load darknet weights
        model.load_darknet_weights(opt.weights_path)
    else:
        # Load checkpoint weights
        model.load_state_dict(torch.load(opt.weights_path, map_location=device))

    model.eval()  # Set in evaluation mode

    dataloader = DataLoader(
        ImageFolder(opt.image_folder, img_size=opt.img_size),
        batch_size=opt.batch_size,
        shuffle=False,
        num_workers=opt.n_cpu,
    )

    classes = load_classes(opt.class_path)  # Extracts class labels from file

    Tensor = torch.cuda.FloatTensor if torch.cuda.is_available() else torch.FloatTensor
    me = MQTTEngine({
        "broker_ip": "192.168.0.31",
        "broker_port": 1883,
        "pub_topic": "/beverage/location"
    })
    me.connect()

    # cap = cv2.VideoCapture('data/cafe7.avi')
    cap = cv2.VideoCapture(0)
    colors = np.random.randint(0, 255, size=(len(classes), 3), dtype="uint8")
    a=[]
    time_begin = time.time()
    NUM = cap.get(cv2.CAP_PROP_FRAME_COUNT)

    target = 'demisoda apple'

    frame_num = 0
    while cap.isOpened():
        ret, img = cap.read()
        if ret is False:
            break

        if (frame_num % 10 != 0):
            frame_num += 1
            continue
        frame_num = 0
        # img = cv2.resize(img, (1280, 960), interpolation=cv2.INTER_CUBIC)

        RGBimg=changeBGR2RGB(img)
        imgTensor = transforms.ToTensor()(RGBimg)
        imgTensor, _ = pad_to_square(imgTensor, 0)
        imgTensor = resize(imgTensor, 416)
        
        imgTensor = imgTensor.unsqueeze(0)
        imgTensor = Variable(imgTensor.type(Tensor))
        

        with torch.no_grad():
            prev_time = time.time()

            detections = model(imgTensor)
            current_time = time.time()
            sec = current_time - prev_time
            fps = 1/sec
            frame_per_sec = "FPS: %0.1f" % fps
            # print(frame_per_sec)


            detections = non_max_suppression(detections, opt.conf_thres, opt.nms_thres)

        a.clear()
        if detections is not None:
            a.extend(detections)
        b=len(a)
        if len(a)  :
            for detections in a:
                if detections is not None:
                    
                    detections = rescale_boxes(detections, opt.img_size, RGBimg.shape[:2])
                    unique_labels = detections[:, -1].cpu().unique()
                    n_cls_preds = len(unique_labels)
                    for x1, y1, x2, y2, conf, cls_conf, cls_pred in detections:
                        if (classes[int(cls_pred)] == target):
                            box_w = x2 - x1
                            box_h = y2 - y1
                            me.publish({
                                'location': int(x1+box_w/2)
                            })
                            print(int(x1+box_w/2))

                        '''    
                        box_w = x2 - x1
                        # print(box_w)
                        box_h = y2 - y1
                        # print(y2, y1)
                        color = [int(c) for c in colors[int(cls_pred)]]
                        #print(cls_conf)
                        img = cv2.rectangle(img, (x1, y1 + box_h), (x2, y1), color, 2)
                        cv2.putText(img, classes[int(cls_pred)], (x1, y1), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                        cv2.putText(img, str("%.2f" % float(conf)), (x2, y2 - box_h), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                    color, 2)
                        '''
                        # print(classes[int(cls_pred)], int(x1+box_w/2), int(480-(y1+box_h/2)))

            #print()
            #print()
        #cv2.putText(img,"Hello World!",(400,50),cv2.FONT_HERSHEY_PLAIN,2.0,(0,0,255),2)

        cv2.imshow('frame', changeRGB2BGR(RGBimg))
        #cv2.waitKey(0)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    # time_end = time.time()
    # time_total = time_end - time_begin
    # print(NUM // time_total)

    cap.release()
    cv2.destroyAllWindows()
    









'''
    capture = cv2.VideoCapture("data/cafe/9.mp4")
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 416)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 416)
    capture.set(cv2.CAP_PROP_FPS, 3)

    colors = np.random.randint(0, 255, size=(len(classes), 3), dtype="uint8")
    capture.set(5, 5)
    print(capture.get(cv2.CAP_PROP_FRAME_WIDTH), capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print("FPS: ", capture.get(5))
    startTime = time.time()
    a=[]
    while capture.isOpened():
        ret, frame = capture.read()
        # print()
        nowTime = time.time()

        PILimg = np.array(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        # RGBimg = changeBGR2RGB(frame)



        imgTensor = transforms.ToTensor()(PILimg)
        imgTensor, _ = pad_to_square(imgTensor, 0)
        imgTensor = resize(imgTensor, 416)
        imgTensor = imgTensor.unsqueeze(0)
        imgTensor = Variable(imgTensor.type(Tensor))

        with torch.no_grad():
            prev_time = time.time()
            detections = model(imgTensor)
            current_time = time.time()
            
            sec = current_time - prev_time
            fps = 1/sec
            frame_per_sec = "FPS: %0.1f" % fps
            # inference_time = datetime.timedelta(seconds=current_time - prev_time)
            prev_time = current_time

            red = (0, 0, 255)
            cv2.putText(frame, frame_per_sec, (25, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, red, 2)
            detections = non_max_suppression(detections, opt.conf_thres, opt.nms_thres)

            a.clear()
            if detections is not None:
                a.extend(detections)
            b=len(a)
            if len(a):
                for detections in a:
                    if detections is not None:
                        detections = rescale_boxes(detections, opt.img_size, PILimg.shape[:2])
                        unique_labels = detections[:, -1].cpu().unique()
                        n_cls_preds = len(unique_labels)
                        for x1, y1, x2, y2, conf, cls_conf, cls_pred in detections:
                            if classes[int(cls_pred)] == 'shrimp cracker':

                                box_w = x2 - x1
                                box_h = y2 - y1
                                color = [int(c) for c in colors[int(cls_pred)]]
                                # print(cls_conf)
                                frame = cv2.rectangle(frame, (x1, y1 + box_h), (x2, y1), color, 2)
                                cv2.putText(frame, classes[int(cls_pred)], (x1, y1), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                                cv2.putText(frame, str("%.2f" % float(conf)), (x2, y2 - box_h), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                            color, 2)
                                print(classes[int(cls_pred)], int(x1+box_w/2), int(224-(y1+box_h/2)))

                print()
            #cv2.putText(img,"Hello World!",(400,50),cv2.FONT_HERSHEY_PLAIN,2.0,(0,0,255),2)
            #cv2.namedWindow('frame', cv2.WINDOW_NORMAL)
            cv2.imshow('frame', frame)

            #cv2.waitKey(0)

            if cv2.waitKey(25) & 0xFF == ord('q'):
                break
    capture.release()
    cv2.destroyAllWindows()

'''

'''
    imgs = []  # Stores image paths
    img_detections = []  # Stores detections for each image index
    print('parameter count: ', count_parameters(model))
    print("\nPerforming object detection:")
    prev_time = time.time()
    for batch_i, (img_paths, input_imgs) in enumerate(dataloader):
        # Configure input
        input_imgs = Variable(input_imgs.type(Tensor))

        # Get detections
        with torch.no_grad():
            detections = model(input_imgs)
            detections = non_max_suppression(detections, opt.conf_thres, opt.nms_thres)
            
        # Log progress
        current_time = time.time()
        inference_time = datetime.timedelta(seconds=current_time - prev_time)
        prev_time = current_time
        print("\t+ Batch %d, Inference Time: %s" % (batch_i, inference_time))

        # Save image and detections
        imgs.extend(img_paths)
        img_detections.extend(detections)

    # Bounding-box colors
    cmap = plt.get_cmap("tab20b")
    colors = [cmap(i) for i in np.linspace(0, 1, 20)]

    print("\nSaving images:")
    # Iterate through images and save plot of detections
    for img_i, (path, detections) in enumerate(zip(imgs, img_detections)):

        print("(%d) Image: '%s'" % (img_i, path))

        # Create plot
        img = np.array(Image.open(path))
        plt.figure()
        fig, ax = plt.subplots(1)
        ax.imshow(img)

        # Draw bounding boxes and labels of detections
        if detections is not None:
            # Rescale boxes to original image
            detections = rescale_boxes(detections, opt.img_size, img.shape[:2])
            unique_labels = detections[:, -1].cpu().unique()
            n_cls_preds = len(unique_labels)
            bbox_colors = random.sample(colors, n_cls_preds)
            for x1, y1, x2, y2, conf, cls_conf, cls_pred in detections:
                
                print("\t+ Label: %s, Conf: %.5f" % (classes[int(cls_pred)], cls_conf.item()))

                box_w = x2 - x1
                box_h = y2 - y1


                color = bbox_colors[int(np.where(unique_labels == int(cls_pred))[0])]
                # Create a Rectangle patch
                bbox = patches.Rectangle((x1, y1), box_w, box_h, linewidth=2, edgecolor=color, facecolor="none")
                # Add the bbox to the plot
                ax.add_patch(bbox)
                # Add label
                plt.text(
                    x1,
                    y1,
                    s=str(classes[int(cls_pred)])+' '+str(int(x1+box_w/2))+ ', '+str(int(y1+box_h/2)),
                    color="white",
                    verticalalignment="top",
                    bbox={"color": color, "pad": 0},
                )

        # Save generated image with detections
        plt.axis("off")
        plt.gca().xaxis.set_major_locator(NullLocator())
        plt.gca().yaxis.set_major_locator(NullLocator())
        filename = path.split("/")[-1].split("\\")[-1].split(".")[0]
        plt.savefig(f"output/{filename}.png", bbox_inches="tight", pad_inches=0.0)
        plt.close()

'''