## Bot Maker

任务型对话控制：

### 对话状态跟踪


* 更新所有NLU槽位信息
* 定义所有类型的数据
* 如果是List类型数据，则需要区分为是否是role
  * slot: entity_name, role_name(默认情况下与 entity_name一致)


### 对话状态管理

* 默认情况下，需要支持 form 表单式澄清数据【最主要的模块】
* 主要流程控制仅需要业务代码逻辑即可


