import asyncio

async def process_prompt(prompt: str) -> str:
    """模拟调用大模型处理任务。"""

    #模拟网络请求或模型推理耗时
    await asyncio.sleep(5)

    #为了测试失败流程，包含“失败”时主动抛出异常
    if "失败" in prompt:
        raise ValueError("模拟模型处理失败")

    return f"模型已完成处理：{prompt}"