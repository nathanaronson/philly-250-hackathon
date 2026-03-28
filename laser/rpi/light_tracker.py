from dataclasses import dataclass

import cv2

import tracker_config as cfg


@dataclass
class LightDetection:
    center_x: int
    center_y: int
    brightness: float
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
    _, max_value, _, max_loc = cv2.minMaxLoc(red)
    annotated = frame.copy()

    if red[max_loc[1], max_loc[0]] < cfg.MIN_RED_VALUE:
        return None, annotated

    threshold_value = max(cfg.MIN_RED_VALUE, int(max_value) - cfg.THRESHOLD_MARGIN)
    red_mask = cv2.inRange(red, threshold_value, 255)
    excess_mask = cv2.inRange(red_excess, cfg.MIN_RED_EXCESS, 255)
    mask = cv2.bitwise_and(red_mask, excess_mask)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, annotated

    best = None
    best_area = 0.0
    best_score = -1.0

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < cfg.MIN_BLOB_AREA:
            continue

        contour_mask = red_mask.copy()
        contour_mask[:] = 0
        cv2.drawContours(contour_mask, [contour], -1, 255, -1)
        score = cv2.mean(red, mask=contour_mask)[0]

        if score > best_score:
            best = contour
            best_area = area
            best_score = score

    if best is None:
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
        brightness=float(best_score),
        area=float(best_area),
        width=width,
        height=height,
    )
    return detection, annotated
