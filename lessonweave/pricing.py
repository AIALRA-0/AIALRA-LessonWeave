"""按调用回执估算 API 等价金额，不把订阅用量写成额外扣款"""

PRICING = {
    'checked_at': '2026-10-20',
    'sources': [
        {'label': 'OpenAI 标准价格', 'url': 'https://developers.openai.com/api/docs/models/gpt-6.1-sol'},
        {'label': 'DeepSeek 官方价格', 'url': 'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/'},
    ],
    'notes': '按标准 API 价格估算，Codex 订阅不会因此另扣 API 费用；未报告的缓存写入费用未计入，Flash 显示空闲至高峰时段的价格范围',
}


def estimate(call):
    values = [call.get(key) for key in ('input_tokens', 'output_tokens', 'cached_input_tokens')]
    if any(value is None for value in values):
        return None
    inputs, outputs, cached = values
    ordinary = max(0, inputs-cached)
    model = call.get('model') or ''
    if model == 'gpt-6.1-sol':
        long_context = inputs > 272000
        amount = (ordinary*(4 if long_context else 2) + cached*(.2 if long_context else .1) + outputs*(15 if long_context else 10))/1e6
        return {'USD': {'minimum': amount, 'maximum': amount}}
    if 'deepseek' in model and 'flash' in model:
        amount = (ordinary + cached*.02 + outputs*4)/1e6
        return {'CNY': {'minimum': amount, 'maximum': amount*2}}
    return None


def usage_totals(calls):
    result = {'calls': len(calls), 'estimated_costs': {}, 'unpriced_calls': 0}
    for field in ('input_tokens', 'output_tokens', 'cached_input_tokens'):
        known = [call[field] for call in calls if call.get(field) is not None]
        result[field] = sum(known) if known else None if calls else 0
        result[field+'_missing_calls'] = len(calls)-len(known)
    for call in calls:
        price = estimate(call)
        if price is None:
            result['unpriced_calls'] += 1
            continue
        for currency, amounts in price.items():
            total = result['estimated_costs'].setdefault(currency, {'minimum': 0, 'maximum': 0})
            for key, value in amounts.items():
                total[key] += value
    return result
