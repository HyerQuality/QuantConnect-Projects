import numpy as np
import cv2
import matplotlib.pyplot as plt

img = cv2.imread('capstone_coins.png', cv2.IMREAD_GRAYSCALE)
orginal_image = cv2.imread('capstone_coins.png', 1)

img = cv2.GaussianBlur(img, (5,5), 0)

circles = cv2.HoughCircles(image=img, method=cv2.HOUGH_GRADIENT, dp=1.2, minDist=300, circles=None, param1=50, param2=30, minRadius=17, maxRadius= 171)


for num, i in enumerate(circles[0, :], start = 1):
    cv2.circle(orginal_image, (i[0], i[1]), i[2], (0,255,0), 4)
    cv2.circle(orginal_image, (i[0], i[1]), 2, (0,0,255), 2)
    cv2.putText(orginal_image, str(num), (i[0], i[1]), cv2.FONT_HERSHEY_SIMPLEX, 2, (0,0,0), 2)

plt.imshow(orginal_image)
plt.show()
