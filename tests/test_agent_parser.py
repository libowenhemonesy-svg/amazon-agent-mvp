from app.agents.parser import parse_agent_response


def test_parse_agent_response_reads_plain_json():
    raw = """
    {
      "summary": "库存低于补货周期，存在断货风险",
      "root_causes": ["可售库存为0", "无在途库存", "补货周期25天"],
      "diagnostic_checks": ["确认补货单", "检查FBA状态"],
      "recommended_actions": ["立即确认补货计划", "暂停广告"],
      "priority": 1,
      "immediate_action_required": true
    }
    """

    result = parse_agent_response(raw, fallback_summary="fallback", severity="high")

    assert result["summary"] == "库存低于补货周期，存在断货风险"
    assert result["root_causes"] == ["可售库存为0", "无在途库存", "补货周期25天"]
    assert result["possible_causes"] == result["root_causes"]
    assert result["recommended_actions"] == ["立即确认补货计划", "暂停广告"]
    assert result["priority"] == 1
    assert result["immediate_action_required"] is True


def test_parse_agent_response_reads_json_fenced_block():
    raw = """
    下面是结果：
    ```json
    {
      "summary": "ACOS高于目标，需要检查广告效率",
      "root_causes": ["花费上升", "转化不足"],
      "diagnostic_checks": ["检查搜索词", "检查CVR"],
      "recommended_actions": ["降低低转化词出价"],
      "priority": 2,
      "immediate_action_required": false
    }
    ```
    """

    result = parse_agent_response(raw, fallback_summary="fallback", severity="medium")

    assert result["summary"] == "ACOS高于目标，需要检查广告效率"
    assert result["priority"] == 2
    assert result["immediate_action_required"] is False


def test_parse_agent_response_falls_back_for_long_plain_text():
    raw = "这是一个非常长的分析报告。" * 100

    result = parse_agent_response(raw, fallback_summary="规则命中异常，需要复核", severity="high")

    assert result["summary"] == "规则命中异常，需要复核"
    assert result["root_causes"]
    assert result["possible_causes"] == result["root_causes"]
    assert result["priority"] == 1
    assert result["immediate_action_required"] is True


def test_parse_agent_response_trims_summary_and_list_lengths():
    raw = {
        "summary": "A" * 100,
        "root_causes": ["1", "2", "3", "4"],
        "diagnostic_checks": ["1", "2", "3", "4", "5"],
        "recommended_actions": ["1", "2", "3", "4", "5"],
        "priority": 9,
        "immediate_action_required": False,
    }

    result = parse_agent_response(raw, fallback_summary="fallback", severity="medium")

    assert len(result["summary"]) <= 60
    assert result["root_causes"] == ["1", "2", "3"]
    assert result["diagnostic_checks"] == ["1", "2", "3", "4"]
    assert result["recommended_actions"] == ["1", "2", "3", "4"]
    assert result["priority"] == 2
