# 餐厅预订系统架构说明

## 系统设计理念

结合自定义逻辑 + Square API，既能精确控制餐桌availability，又能让用户收到Square的短信通知。

---

## 核心组件

### 1. 餐桌容量管理（自定义逻辑）

**位置**: `services/square_service.py` → `check_availability()` + `_can_book_at_time()`

**餐厅配置**:
- 1张2人桌（可容纳1-2人）
- 1张4人桌（可容纳3-4人）
- 用餐时长：90分钟
- 营业时间：14:00-22:00（2pm-10pm），每30分钟一个时间段

**逻辑流程**:
```python
def check_availability(date, party_size, preferred_time):
    1. 从Square获取该日期所有现有预订
    2. 根据party_size确定需要的桌子:
       - 1-2人 → 需要2人桌
       - 3-4人 → 需要4人桌
       - >4人 → 无法容纳

    3. 遍历所有时间段（14:00-22:00，30分钟间隔）
    4. 对每个时间段检查:
       - 是否与现有预订时间冲突（考虑90分钟用餐时长）
       - 同样大小的桌子是否已被占用

    5. 返回所有可用时间段
```

**示例**:
- 如果6pm已有4人桌预订，占用时间：18:00-19:30
- 那么17:00, 17:30也不能订4人桌（会冲突）
- 但2人桌不受影响，依然可以预订

---

### 2. 预订创建（Square API）

**位置**: `services/square_service.py` → `create_booking()`

**为什么用Square创建**:
- ✅ 用户自动收到Square的短信确认
- ✅ 预订记录在Square后台可见
- ✅ 可以通过Square管理和查看

**流程**:
```python
def create_booking(date, time, party_size, name, phone):
    1. 创建或查找客户（by phone number）
    2. 转换时间：本地时间(PST) → UTC (+8小时)
    3. 调用Square Bookings API创建预订:
       - location_id: LGHY7R3KJADYX
       - service_variation_id: LPFNCRAESICB2W4U7WUM7QFD
       - team_member_id: TMr0EtehupeqKvro
       - duration: 90分钟
       - customer_note: "Party size: X"

    4. 返回booking_id
```

**重要**:
- 时区转换很关键！本地7:30pm = UTC次日3:30am
- party_size存在`customer_note`字段

---

### 3. 取消预订（Square API）

**位置**: `services/square_service.py` → `cancel_booking()`

**流程**:
```python
def cancel_booking(booking_id):
    1. 调用Square API: POST /v2/bookings/{booking_id}/cancel
    2. Square自动发送取消短信给用户
    3. 返回成功/失败状态
```

---

### 4. 查找预订（Square API）

**位置**: `services/square_service.py` → `find_booking_by_name_and_date()`

**用途**: 用户要取消时，通过姓名+日期查找booking_id

**流程**:
```python
def find_booking_by_name_and_date(customer_name, date):
    1. 获取所有active预订
    2. 筛选指定日期的预订
    3. 返回第一个匹配的预订详情
```

**注意**: 不要问用户booking ID，他们不知道！

---

## 对话流程（Booking Agent）

**位置**: `agents/booking_agent.py`

### 预订流程

1. **用户问availability**: "do you have a table for 3 tonight?"
   - Agent调用`check_availability(today, 3, None)`
   - 自定义逻辑计算可用时间段
   - Agent: "Certainly! We have tables available at [times]"

2. **用户选择时间**: "7pm works"
   - Agent记录时间
   - Agent: "Great! May I have your name, please?"

3. **用户提供姓名**: "John Smith"
   - Agent记录姓名
   - Agent: "And may I have a phone number?"

4. **用户提供电话**: "415-555-1234"
   - Agent调用`create_booking()`
   - Square创建预订 + 发送短信 ✓
   - Agent: "Perfect! Let me confirm: John Smith, party of 3, tonight at 7:00 PM..."

### 取消流程

1. **用户要取消**: "I want to cancel my reservation"
   - Agent: "May I have your name?"

2. **用户提供姓名**: "John Smith"
   - Agent: "What date was your reservation for?"

3. **用户说日期**: "tomorrow"
   - Agent调用`find_booking_by_name_and_date()`
   - Agent: "I found your reservation for tomorrow at 7pm for 3 guests. Is this correct?"

4. **用户确认**: "yes"
   - Agent调用`cancel_booking(booking_id)`
   - Square取消预订 + 发送取消短信 ✓
   - Agent: "Your reservation has been cancelled. Thank you!"

---

## 关键优势

### ✅ 自定义逻辑的好处
- 完全控制餐桌分配规则
- 不需要升级到Square Appointments Premium ($69/月)
- 可以随时调整规则（例如增加桌子数量）

### ✅ Square API的好处
- 用户自动收到短信通知
- 餐厅可以在Square后台查看预订
- 标准化的预订管理

### ✅ 组合方案
- 最低成本：只需Square Plus ($49/月)
- 最大灵活性：自己控制availability逻辑
- 最佳用户体验：自动短信通知

---

## 测试方式

### 测试自定义availability逻辑
```bash
python3 test_availability_logic.py
```

### 测试完整对话流程
```bash
python3 test_chat.py
```

### 测试完整系统（availability + 预订）
```bash
python3 test_complete_system.py
```

---

## 配置信息

### Square Production API
- Access Token: `EAAAl1_zkoWSi9MIBhzh4BzMV-YZmIgFVpXCx89eTnboFQDTru-1cke4WfxmrXgM`
- Location ID: `LGHY7R3KJADYX`
- Service Variation ID: `LPFNCRAESICB2W4U7WUM7QFD`
- Team Member ID: `TMr0EtehupeqKvro`
- Environment: `production`

### 其他API
- OpenAI: GPT-4o-mini (对话逻辑)
- Deepgram: 语音识别和合成
- Twilio: 电话接入（待审批）

---

## 下一步

1. ✅ 自定义availability逻辑 - 完成
2. ✅ Square预订集成 - 完成
3. ✅ 简化prompt - 完成
4. ⏳ 等待Twilio审批
5. ⏳ 测试完整语音通话流程

---

## 成本总结

- Square Plus: $49/月
- OpenAI API: 按使用量
- Deepgram: 按使用量
- Twilio: 按使用量

**总计**: 约$50-100/月（取决于通话量）

**省下的钱**:
- ❌ 不需要Square Appointments Premium: $69/月
- ❌ 不需要OpenTable Partner: 价格未知，可能>$100/月
