import cv2
import numpy as np
from collections import deque
from ultralytics import YOLO
from typing import List, Dict, Any, Optional

class StudentTracker:
    """
    学生状态追踪器（时序平滑）
    用于解决单帧检测带来的数据抖动问题
    """
    def __init__(self, window_size: int = 10):
        self.window_size = window_size
        self.score_history = deque(maxlen=window_size)
        
    def update_score(self, raw_score: float) -> float:
        """更新历史分数并返回平滑后的分数"""
        self.score_history.append(raw_score)
        return sum(self.score_history) / len(self.score_history)


class BehaviorAnalyzer:
    def __init__(self, model_path: str = 'yolov8n-pose.pt'):
        """
        初始化分析器，加载模型（仅加载一次，提升性能）
        """
        try:
            self.model = YOLO(model_path)
            print(f"✅ 成功加载姿态模型: {model_path}")
        except Exception as e:
            print(f"❌ 模型加载失败: {e}")
            self.model = None
            
        # 用于存储每个学生的追踪器（以检测框的左上角坐标作为简易ID）
        self.trackers: Dict[tuple, StudentTracker] = {}

    def analyze_frames(self, frames: List[Dict]) -> Dict[str, Any]:
        """分析帧数据"""
        if not self.model:
            return {'error': '模型未加载'}

        all_student_data = []
        
        for frame_data in frames:
            frame = frame_data['frame']
            timestamp = frame_data['timestamp']
            
            # 推理：检测人体关键点
            results = self.model(frame, conf=0.5, verbose=False, classes=[0]) # 只检测人
            
            current_frame_ids = set() # 记录当前帧出现的ID，用于清理离开画面的学生
            
            for result in results:
                if result.keypoints is not None:
                    keypoints = result.keypoints.xy.cpu().numpy()
                    boxes = result.boxes.xyxy.cpu().numpy()
                    
                    for i, box in enumerate(boxes):
                        x1, y1, x2, y2 = map(int, box)
                        tracker_id = (x1, y1) # 简易ID
                        current_frame_ids.add(tracker_id)
                        
                        # 获取或创建该学生的追踪器
                        if tracker_id not in self.trackers:
                            self.trackers[tracker_id] = StudentTracker(window_size=10)
                            
                        # 提取关键点
                        face_kps = keypoints[i][0:5] # 鼻子、左眼、右眼、左耳、右耳
                        hand_kps = keypoints[i][9:13] # 左手腕、右手腕等
                        
                        # 计算原始专注度
                        raw_score = self._calculate_raw_attention(face_kps, hand_kps, frame.shape)
                        
                        # 时序平滑
                        smoothed_score = self.trackers[tracker_id].update_score(raw_score)
                        
                        all_student_data.append({
                            'timestamp': timestamp,
                            'position': (x1, y1, x2, y2),
                            'attention_score': round(smoothed_score, 2),
                            'is_attending': smoothed_score > 70
                        })
            
            # 清理离开画面的学生追踪器，防止内存泄漏
            for tid in list(self.trackers.keys()):
                if tid not in current_frame_ids:
                    del self.trackers[tid]

        return self._generate_summary(all_student_data)

    def _calculate_raw_attention(self, face_kps, hand_kps, img_shape) -> float:
        """
        基于姿态估计的专注度算法（优化版）
        """
        nose = face_kps[0]
        left_ear = face_kps[3]
        right_ear = face_kps[4]
        left_wrist = hand_kps[0]
        right_wrist = hand_kps[1]
        
        # 基础分
        score = 80.0
        
        # 规则1: 头部偏转检测（歪头/低头）
        # 如果左右耳高度差大于 20 像素，认为在歪头或低头
        head_tilt = abs(left_ear[1] - right_ear[1])
        if head_tilt > 20:
            # 规则2: 记笔记豁免机制
            # 如果低头，但手腕的 Y 坐标大于鼻子的 Y 坐标（说明手在脸下方），判定为记笔记
            is_taking_notes = False
            if nose[1] > 0: # 确保鼻子被检测到
                if left_wrist[1] > nose[1] or right_wrist[1] > nose[1]:
                    is_taking_notes = True
            
            if is_taking_notes:
                score += 10  # 记笔记加分
            else:
                score -= 20  # 纯低头/睡觉扣分
                
        # 规则3: 关键点缺失惩罚
        # 如果鼻子或耳朵坐标为 (0,0)，说明被遮挡或背对镜头
        if nose[0] == 0 and nose[1] == 0:
            score -= 30
            
        return max(0, min(100, score))

    def _generate_summary(self, student_data: List[Dict]) -> Dict[str, Any]:
        """生成统计汇总"""
        if not student_data:
            return {'total_samples': 0, 'avg_attention': 0, 'min_attention': 0, 'max_attention': 0, 'detailed_data': []}
            
        scores = [s['attention_score'] for s in student_data]
        return {
            'total_samples': len(student_data),
            'avg_attention': float(np.mean(scores)),
            'min_attention': float(np.min(scores)),
            'max_attention': float(np.max(scores)),
            'detailed_data': student_data
        }