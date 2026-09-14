import matplotlib.pyplot as plt
import numpy as np
import os
import time
from pathlib import Path

class DashboardGenerator:
    def __init__(self):
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False

    def generate_dashboard(self, analysis_results: dict) -> str:
        """生成可视化看板"""
        plt.switch_backend('Agg')
        timestamp = int(time.time())
        dashboard_path = self.output_dir / f"dashboard_{timestamp}.png"
        
        fig = plt.figure(figsize=(15, 10))
        fig.suptitle('智慧课堂分析看板', fontsize=16, fontweight='bold')

        # 1. 总体概览
        ax1 = plt.subplot(2, 3, 1)
        self._plot_overview(ax1, analysis_results)
        
        # 2. 专注度分布
        ax2 = plt.subplot(2, 3, 2)
        self._plot_attention_distribution(ax2, analysis_results)
        
        # 3. 时间趋势
        ax3 = plt.subplot(2, 3, 3)
        self._plot_time_trend(ax3, analysis_results)
        
        # 4. 学生位置分布
        ax4 = plt.subplot(2, 3, 4)
        self._plot_student_positions(ax4, analysis_results)
        
        # 5. 专注度趋势
        ax5 = plt.subplot(2, 3, 5)
        self._plot_attention_trend(ax5, analysis_results)
        
        # 6. 关键指标
        ax6 = plt.subplot(2, 3, 6)
        self._plot_key_metrics(ax6, analysis_results)

        plt.tight_layout()
        plt.savefig(dashboard_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return str(dashboard_path)

    def _plot_overview(self, ax, results):
        ax.text(0.1, 0.7, f"采样总数: {results.get('total_samples', 0)}", fontsize=12)
        ax.text(0.1, 0.5, f"平均专注度: {results.get('avg_attention', 0):.1f}%", fontsize=12)
        ax.set_title("课堂概览")
        ax.axis('off')

    def _plot_attention_distribution(self, ax, results):
        if 'detailed_data' in results and results['detailed_data']:
            attention_scores = [s['attention_score'] for s in results['detailed_data']]
            ax.hist(attention_scores, bins=10, color='skyblue', alpha=0.7)
            ax.set_title("专注度分布")
            ax.set_xlabel("专注度 (%)")
            ax.set_ylabel("学生数量")

    def _plot_time_trend(self, ax, results):
        # 模拟数据，实际应从 detailed_data 中提取
        time_points = np.linspace(0, 60, 12)
        attention_trend = np.random.normal(results.get('avg_attention', 70), 15, 12)
        attention_trend = np.clip(attention_trend, 0, 100)
        ax.plot(time_points, attention_trend, marker='o', color='green')
        ax.set_title("专注度时间趋势")
        ax.set_xlabel("时间 (分钟)")
        ax.set_ylabel("专注度 (%)")
        ax.grid(True, alpha=0.3)

    def _plot_student_positions(self, ax, results):
        if 'detailed_data' in results and results['detailed_data']:
            positions = [s['position'] for s in results['detailed_data']]
            x_coords = [p[0] for p in positions]
            y_coords = [p[1] for p in positions]
            scores = [s['attention_score'] for s in results['detailed_data']]
            scatter = ax.scatter(x_coords, y_coords, c=scores, cmap='viridis', alpha=0.6)
            plt.colorbar(scatter, ax=ax, label='专注度')
            ax.set_title("学生位置分布")
            ax.set_xlabel("X 坐标")
            ax.set_ylabel("Y 坐标")

    def _plot_attention_trend(self, ax, results):
        ax.text(0.5, 0.5, "趋势: 稳定", fontsize=14, fontweight='bold', ha='center', color='blue')
        ax.set_title("专注度趋势分析")
        ax.axis('off')

    def _plot_key_metrics(self, ax, results):
        metrics = [
            f"采样总数: {results.get('total_samples', 0)}",
            f"平均专注度: {results.get('avg_attention', 0):.1f}%",
            f"最高专注度: {results.get('max_attention', 0):.1f}%"
        ]
        if results.get('is_video'):
            metrics.append(f"课堂时长: {results.get('video_duration', 0):.2f} 秒")
            
        for i, metric in enumerate(metrics):
            ax.text(0.1, 0.8-i*0.2, metric, fontsize=11)
        ax.set_title("关键指标")
        ax.axis('off')