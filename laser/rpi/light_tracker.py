from dataclasses import dataclass

import cv2

import tracker_config as cfg


@dataclass
class LightDetection:
    center_x: int
    center_y: int
    score: float
    area: float
    width: int
    height: int


def detect_light(frame):
    height, width = frame.shape[:2]
    blurred = cv2.GaussianBlur(frame, (cfg.BLUR_KERNEL, cfg.BLUR_KERNEL), 0)
    blue = blurred[:, :, 0]
    green = blurred[:, :, 1]
    red = blurred[:, :, 2]

    red_excess = cv2.subtract(red, cv2.max(blue, green))
    _, max_value, _, max_loc = cv2.minMaxLoc(red_excess)
    annotated = frame.copy()

    if max_value < cfg.MIN_RED_EXCESS:
        return None, annotated

    red_mask = cv2.inRange(red, cfg.MIN_RED_VALUE, 255)
    excess_mask = cv2.inRange(red_excess, cfg.MIN_RED_EXCESS, 255)
    mask = cv2.bitwise_and(red_mask, excess_mask)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, annotated

    best = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(best)
    if area < cfg.MIN_BLOB_AREA:
        return None, annotated

    moments = cv2.moments(best)
    if moments["m00"] > 0.0:
        center_x = int(moments["m10"] / moments["m00"])
        center_y = int(moments["m01"] / moments["m00"])
    else:
        center_x, center_y = max_loc

    cv2.drawContours(annotated, [best], -1, (0, 255, 0), 2)
    cv2.circle(annotated, (center_x, center_y), 6, (0, 0, 255), -1)
    cv2.circle(annotated, (width // 2, height // 2), 6, (255, 0, 0), -1)

    detection = LightDetection(
        center_x=center_x,
        center_y=center_y,
        score=float(max_value),
        area=float(area),
        width=width,
        height=height,
    )
    return detection, annotated
