import cv2
import threading
import time
import queue

cap = cv2.VideoCapture('data/cafe2/cafe3.avi')
q = queue.Queue()
FrameNum = 0

while (True):
    ret, frame = cap.read()
    if ret is False:
        break
    if (FrameNum != 60):  
        q.put(frame)
        FrameNum += 1

    elif (FrameNum == 60):
        FrameNum = 0
        q.get_nowait()
        cv2.imshow('frame', frame)

        if (cv2.waitKey(25) & 0xFF == ord('q')):
            break