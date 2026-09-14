import os
import time
import json
from typing import Dict, Any

# 请确保已安装 dashscope SDK: pip install dashscope
try:
    import dashscope
    from dashscope import Generation
except ImportError:
    print("警告: 未安装 dashscope SDK。千问API功能将不可用。请运行 'pip install dashscope'")
    dashscope = None

class QwenIntegration:
    def __init__(self):
        """
        初始化千问集成。
        请确保已设置环境变量 DASHSCOPE_API_KEY，或在此处直接赋值。
        """
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            print("警告: 未找到 DASHSCOPE_API_KEY 环境变量。千问API调用将失败。")
        else:
            dashscope.api_key = self.api_key

    def generate_suggestions(self, analysis_results: Dict[str, Any]) -> str:
        """
        基于分析结果，调用千问大模型生成智能教学建议。
        """
        if not self.api_key or not dashscope:
            return self._generate_local_fallback_suggestions(analysis_results)

        try:
            return self._call_qwen_api(analysis_results)
        except Exception as e:
            print(f"调用千问API失败: {e}。正在生成本地建议...")
            return self._generate_local_fallback_suggestions(analysis_results)

    def _call_qwen_api(self, analysis_results: Dict[str, Any]) -> str:
        """调用千问API生成建议"""
        prompt = self._build_prompt(analysis_results)

        response = Generation.call(
            model='qwen-plus', # 可以根据需要更换模型，如 qwen-turbo, qwen-max
            messages=[
                {'role': 'system', 'content': '你是一位经验丰富的教学督导专家，擅长通过课堂数据分析教学效果，并给出具体、可执行的改进建议。'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.7,
        )

        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            raise Exception(f"API调用失败: Code={response.status_code}, Message={response.message}")

    def _build_prompt(self, data: Dict[str, Any]) -> str:
        """构建发送给大模型的提示词"""
        return f"""
        请根据以下智慧课堂的分析数据，生成一份专业的教学分析报告和建议。

        **课堂数据概览:**
        - **总采样数 (学生*帧):** {data.get('total_samples', 0)}
        - **平均专注度:** {data.get('avg_attention', 0):.2f}%
        - **最低专注度:** {data.get('min_attention', 0):.2f}%
        - **最高专注度:** {data.get('max_attention', 0):.2f}%
        - **课堂类型:** {'视频' if data.get('is_video') else '图片'}
        - **课堂时长:** {data.get('video_duration', 0):.2f} 秒

        **要求:**
        1.  **分析现状**：简要评价当前的课堂专注度水平。
        2.  **提出建议**：针对专注度偏低的情况，给出至少3条具体的教学改进建议（如增加互动、调整节奏、使用多媒体等）。
        3.  **格式清晰**：分点陈述，语言专业且富有建设性。
        """

    def _generate_local_fallback_suggestions(self, analysis_results: Dict[str, Any]) -> str:
        """
        当API不可用时，使用本地规则生成简单的建议作为降级方案。
        """
        avg_attention = analysis_results.get('avg_attention', 0)
        suggestions = []
        
        suggestions.append("### 智能分析建议 (本地模式)")
        suggestions.append("*(注：因API密钥未配置或调用失败，以下为基于规则的简单建议)*\n")

        if avg_attention < 60:
            suggestions.append("1.  **专注度预警**：学生平均专注度较低，建议立即引入互动环节，如提问或小组讨论，以重新吸引学生注意力。")
            suggestions.append("2.  **调整节奏**：检查教学内容是否过于枯燥或难度过高，适当放缓节奏或穿插趣味案例。")
        elif avg_attention < 80:
            suggestions.append("1.  **专注度良好**：大部分学生能跟上教学节奏。可以尝试引入更多开放式问题，激发深度思考。")
            suggestions.append("2.  **关注个体**：留意专注度较低的学生，课后可以进行简单沟通了解原因。")
        else:
            suggestions.append("1.  **效果优秀**：学生专注度非常高，当前教学方法和内容极具吸引力，请继续保持。")
            suggestions.append("2.  **深化学习**：可以在现有基础上，增加一些拓展性内容，满足学有余力学生的需求。")
            
        return "\n".join(suggestions)