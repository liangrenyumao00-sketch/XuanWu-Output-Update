# 贡献指南

感谢您对 XuanWu OCR 项目的关注！本指南将帮助您了解如何为项目做出贡献。

## 🤝 如何贡献

### 贡献方式
- **报告问题**: 在GitHub Issues中报告bug或提出功能请求
- **提交代码**: 通过Pull Request提交代码改进
- **改进文档**: 完善项目文档和帮助信息
- **测试反馈**: 测试新功能并提供反馈
- **社区支持**: 帮助其他用户解决问题

### 贡献流程
1. Fork项目到您的GitHub账户
2. 创建功能分支进行开发
3. 提交代码并编写测试
4. 确保代码通过所有检查
5. 提交Pull Request

## 🐛 报告问题

### Bug报告模板
```markdown
## Bug描述
简要描述遇到的问题

## 重现步骤
1. 执行操作...
2. 点击按钮...
3. 观察结果...

## 预期行为
描述您期望的正常行为

## 实际行为
描述实际发生的情况

## 环境信息
- 操作系统: Windows 10
- Python版本: 3.9.7
- 程序版本: 2.1.9
- 其他相关信息

## 截图/日志
如果有相关截图或错误日志，请附上

## 附加信息
任何其他相关信息
```

### 功能请求模板
```markdown
## 功能描述
简要描述您希望添加的功能

## 使用场景
描述这个功能的使用场景和价值

## 详细说明
详细描述功能的期望行为和实现方式

## 替代方案
如果有其他解决方案，请说明

## 附加信息
任何其他相关信息
```

## 💻 代码贡献

### 开发环境设置
```bash
# 1. Fork并克隆项目
git clone https://github.com/your-username/XuanWu-Output-Update.git
cd XuanWu-Output-Update

# 2. 添加上游仓库
git remote add upstream https://github.com/liangrenyumao00-sketch/XuanWu-Output-Update.git

# 3. 创建开发环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 4. 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 5. 安装pre-commit钩子
pre-commit install
```

### 分支管理
```bash
# 创建功能分支
git checkout -b feature/new-feature

# 或者修复bug分支
git checkout -b bugfix/fix-issue-123

# 或者文档分支
git checkout -b docs/update-readme
```

### 代码规范
- 遵循 [代码规范](coding-standards.md)
- 使用 Black 格式化代码
- 使用 flake8 检查代码风格
- 使用 mypy 进行类型检查
- 编写单元测试和集成测试

### 提交信息规范
```bash
# 提交信息格式
<类型>(<范围>): <描述>

# 示例
feat(ocr): 添加Google Vision OCR支持
fix(ui): 修复窗口大小调整问题
docs(readme): 更新安装说明
test(core): 添加OCR模块单元测试
refactor(api): 重构API调用逻辑
```

### 提交类型
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具的变动

## 🧪 测试要求

### 单元测试
```python
# tests/unit/test_ocr_worker.py
import pytest
from unittest.mock import Mock, patch
from core.ocr_worker import OCRWorker

class TestOCRWorker:
    def test_initialization(self):
        worker = OCRWorker()
        assert worker.is_running == False
        
    @patch('core.ocr_worker.requests.post')
    def test_api_call(self, mock_post):
        mock_post.return_value.json.return_value = {
            'words_result': [{'words': 'test'}]
        }
        
        worker = OCRWorker()
        result = worker.recognize_text('test_image')
        
        assert result == 'test'
        mock_post.assert_called_once()
```

### 集成测试
```python
# tests/integration/test_api_integration.py
import pytest
from core.api.baidu_api import BaiduAPI

class TestBaiduAPIIntegration:
    @pytest.fixture
    def api(self):
        return BaiduAPI('test_key', 'test_secret')
        
    def test_api_initialization(self, api):
        assert api.api_key == 'test_key'
        assert api.secret_key == 'test_secret'
```

### 测试覆盖率
- 新功能测试覆盖率应达到 80% 以上
- 关键模块测试覆盖率应达到 90% 以上
- 所有测试必须通过才能合并

## 📝 文档贡献

### 文档类型
- **用户文档**: 用户手册、快速开始指南、FAQ
- **开发者文档**: API文档、开发指南、架构说明
- **代码文档**: 函数和类的文档字符串
- **示例代码**: 使用示例和最佳实践

### 文档规范
- 使用Markdown格式编写
- 遵循项目文档风格
- 提供清晰的示例代码
- 保持文档与代码同步更新

### 文档更新流程
1. 确定文档更新范围
2. 编写或修改文档内容
3. 检查语法和格式
4. 提交Pull Request
5. 等待代码审查

## 🔍 代码审查

### 审查标准
- **功能正确性**: 代码是否实现了预期功能
- **代码质量**: 代码是否清晰、可维护
- **性能考虑**: 是否有性能问题或优化空间
- **安全性**: 是否存在安全漏洞
- **测试覆盖**: 是否有足够的测试覆盖

### 审查流程
1. 自动检查通过（CI/CD）
2. 至少一名维护者审查
3. 解决审查意见
4. 维护者批准合并

### 审查清单
- [ ] 代码符合项目规范
- [ ] 功能实现正确
- [ ] 测试覆盖充分
- [ ] 文档更新完整
- [ ] 性能影响评估
- [ ] 安全性检查通过

## 🚀 发布流程

### 版本管理
- 使用语义化版本控制 (SemVer)
- 主版本号：不兼容的API修改
- 次版本号：向下兼容的功能性新增
- 修订号：向下兼容的问题修正

### 发布检查清单
- [ ] 所有测试通过
- [ ] 文档更新完整
- [ ] 版本号正确更新
- [ ] CHANGELOG更新
- [ ] 构建包测试通过
- [ ] 发布说明准备

## 🏷️ 标签和里程碑

### Issue标签
- `bug`: 错误报告
- `enhancement`: 功能请求
- `documentation`: 文档相关
- `good first issue`: 适合新手的任务
- `help wanted`: 需要帮助的任务
- `priority: high`: 高优先级
- `priority: low`: 低优先级

### Pull Request标签
- `ready for review`: 准备审查
- `work in progress`: 开发中
- `needs testing`: 需要测试
- `breaking change`: 破坏性变更

## 👥 社区参与

### 讨论渠道
- **GitHub Issues**: 问题讨论和功能请求
- **GitHub Discussions**: 一般讨论和问答
- **邮件列表**: 重要公告和深度讨论

### 行为准则
- 尊重所有参与者
- 欢迎不同观点和经验水平
- 专注于对社区最有利的事情
- 对其他社区成员表示同理心和友善

### 获得帮助
- 查看现有文档和FAQ
- 搜索已关闭的Issues
- 在Discussions中提问
- 联系维护者获取帮助

## 🎯 新手入门

### 适合新手的任务
- 文档改进和翻译
- 简单的bug修复
- 测试用例编写
- 代码示例添加
- 性能优化建议

### 推荐学习路径
1. 阅读项目README和文档
2. 运行项目并熟悉功能
3. 查看代码结构和架构
4. 从简单的任务开始贡献
5. 逐步参与更复杂的功能开发

### 获取指导
- 寻找标记为 `good first issue` 的任务
- 在Discussions中寻求指导
- 联系维护者获得一对一的帮助

## 📋 贡献检查清单

### 提交前检查
- [ ] 代码遵循项目规范
- [ ] 所有测试通过
- [ ] 文档更新完整
- [ ] 提交信息清晰
- [ ] 分支名称合理

### Pull Request检查
- [ ] 描述清楚变更内容
- [ ] 关联相关Issue
- [ ] 添加必要的标签
- [ ] 请求适当的审查者
- [ ] 更新相关文档

## 🏆 贡献者认可

### 贡献者类型
- **核心维护者**: 负责项目主要维护工作
- **活跃贡献者**: 定期提交代码和问题修复
- **文档贡献者**: 专注于文档改进
- **测试贡献者**: 提供测试反馈和测试用例
- **社区贡献者**: 帮助用户和推广项目

### 认可方式
- 在README中列出贡献者
- 在发布说明中感谢贡献者
- 给予贡献者适当的权限
- 提供贡献者证书

## 📞 联系我们

### 维护者
- **主要维护者**: [维护者姓名](mailto:maintainer@example.com)
- **技术问题**: [技术维护者](mailto:tech@example.com)
- **文档问题**: [文档维护者](mailto:docs@example.com)

### 联系方式
- **GitHub**: [项目主页](https://github.com/liangrenyumao00-sketch/XuanWu-Output-Update)
- **Issues**: [问题反馈](https://github.com/liangrenyumao00-sketch/XuanWu-Output-Update/issues)
- **Discussions**: [社区讨论](https://github.com/liangrenyumao00-sketch/XuanWu-Output-Update/discussions)

---

*感谢您的贡献！每一个贡献都让项目变得更好。*
