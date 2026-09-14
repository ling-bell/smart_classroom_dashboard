import sys
import time
import os
from video_processor import VideoProcessor
from behavior_analyzer import BehaviorAnalyzer
from dashboard_generator import DashboardGenerator
from qwen_integration import QwenIntegration

class SmartClassroomDashboard:
    def __init__(self):
        self.video_processor = VideoProcessor()
        self.behavior_analyzer = BehaviorAnalyzer()
        self.dashboard_generator = DashboardGenerator()
        self.qwen_integration = QwenIntegration()

    def run_analysis(self, file_path):
        """执行完整的课堂分析流程（支持图片和视频）"""
        print(f"开始分析文件：{file_path}")
        
        # 1. 判断文件类型并处理
        file_ext = os.path.splitext(file_path)[1].lower()
        is_video = file_ext in ['.mp4', '.avi', '.mov', '.mkv']
        is_image = file_ext in ['.jpg', '.jpeg', '.png', '.bmp']
        
        if not (is_video or is_image):
            raise Exception("不支持的文件格式，请上传图片或视频文件")

        print(f"1. 正在处理{'视频' if is_video else '图片'}文件...")
        # 统一处理流程，获取帧数据和视频时长（如果是视频）
        frames, video_duration = self.video_processor.process(file_path, is_video)

        # 2. 行为分析
        print("2. 正在分析学生行为...")
        analysis_results = self.behavior_analyzer.analyze_frames(frames)
        analysis_results['is_video'] = is_video
        analysis_results['video_duration'] = video_duration

        # 3. 数据可视化
        print("3. 正在生成看板...")
        dashboard_path = self.dashboard_generator.generate_dashboard(analysis_results)

        # 4. 生成智能报告
        print("4. 正在生成智能分析报告...")
        suggestions = self.qwen_integration.generate_suggestions(analysis_results)
        report_path = self.generate_report(analysis_results, suggestions, dashboard_path)

        print(f"分析完成！看板已生成：{dashboard_path}")
        print(f"报告已生成：{report_path}")
        return dashboard_path, report_path

    def generate_report(self, analysis_results, suggestions, dashboard_path):
        """生成分析报告"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_path = f"output/report_{timestamp}.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# 智慧课堂分析报告\n\n")
            f.write(f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("## 课堂概览\n")
            f.write(f"- 总学生数：{analysis_results.get('total_samples', 0)}\n")
            f.write(f"- 平均专注度：{analysis_results.get('avg_attention', 0):.2f}%\n")
            if analysis_results.get('is_video'):
                f.write(f"- 课堂时长：{analysis_results.get('video_duration', 0):.2f} 秒\n")
            f.write("\n## 分析看板\n")
            f.write(f" ![看板截图]({dashboard_path}) \n\n")
            f.write("## 智能分析建议\n")
            f.write(suggestions + "\n\n")
        return report_path

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python main.py <图片或视频文件路径>")
        sys.exit(1)
    file_path = sys.argv[1]
    dashboard = SmartClassroomDashboard()
    dashboard.run_analysis(file_path)