import cv2
import os
from pathlib import Path
from ultralytics import YOLO
from typing import List, Dict, Tuple

class VideoProcessor:
    def __init__(self, model_path='yolov8n.pt'):
        """初始化处理器，加载用于标注的YOLO模型"""
        self.model = YOLO(model_path)
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)

    def process(self, file_path: str, is_video: bool) -> Tuple[List[Dict], float]:
        """处理视频或图片，并生成带标注的文件"""
        if is_video:
            return self._process_video(file_path)
        else:
            return self._process_image(file_path)

    def _process_video(self, video_path: str) -> Tuple[List[Dict], float]:
        """处理视频，抽帧并生成标注视频"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception("无法打开视频文件")

        # 获取视频信息
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps

        # 定义视频编码器和创建VideoWriter对象
        output_video_path = self.output_dir / "annotated_video.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(output_video_path), fourcc, fps, (width, height))

        frames = []
        frame_count = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # 每隔30帧处理一次，提高效率
                if frame_count % 30 == 0: 
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    annotated_frame = self._annotate_frame(rgb_frame.copy())
                    
                    # 保存用于后续分析的关键帧
                    frames.append({
                        'frame': rgb_frame,
                        'timestamp': frame_count / fps,
                        'frame_index': frame_count
                    })
                    
                    # 写入标注后的帧
                    out.write(cv2.cvtColor(annotated_frame, cv2.COLOR_RGB2BGR))
                
                frame_count += 1
        finally:
            # 确保资源释放
            cap.release()
            out.release()
            
        print(f"视频处理完成，标注视频已保存至: {output_video_path}")
        return frames, duration

    def _process_image(self, image_path: str) -> Tuple[List[Dict], float]:
        """处理图片，并生成标注图片"""
        img = cv2.imread(image_path)
        if img is None:
            raise Exception("无法读取图片文件")
        
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        annotated_img = self._annotate_frame(rgb_img.copy())
        
        # 保存标注后的图片
        output_image_path = self.output_dir / "annotated_image.jpg"
        cv2.imwrite(str(output_image_path), cv2.cvtColor(annotated_img, cv2.COLOR_RGB2BGR))
        print(f"图片处理完成，标注图片已保存至: {output_image_path}")
        
        return [{
            'frame': rgb_img,
            'timestamp': 0,
            'frame_index': 0
        }], 0

    def _annotate_frame(self, frame) -> any:
        """使用YOLO模型对单帧图像进行标注"""
        # 使用YOLO进行推理，只检测 'person' 类别
        results = self.model(frame, classes=[0], conf=0.25, verbose=False)
        annotated_frame = frame.copy()
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                # 获取边界框坐标
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = box.conf[0].item()
                
                # 绘制矩形框和标签
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = f"Student {conf:.2f}"
                cv2.putText(annotated_frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
        return annotated_frame