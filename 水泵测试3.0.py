import network
import time
from umqtt.simple import MQTTClient
from machine import Pin, ADC, reset

# Wi-Fi 和 MQTT 信息
SSID = "USER_EC76D0"
PASSWORD = "76295803"
EMQX_SERVER = "broker.emqx.io"
EMQX_PORT = 1883
EMQX_CLIENT_ID = "test_client_id"
EMQX_TOPIC_WATER = b"alex/water"
EMQX_TOPIC_MOISTURE = b"alex/moisture"
MQTT_KEEPALIVE = 60  # MQTT 保活时间为 60 秒

# 初始化硬件
relay = Pin(13, Pin.OUT)  # 水泵继电器连接 Pin 13
soil_sensor = ADC(Pin(33))  # 湿度传感器连接 Pin 15
soil_sensor.atten(ADC.ATTN_11DB)

# 初始化 EMQX 状态指示灯
emqx_led = Pin(2, Pin.OUT)  # LED 指示灯连接 Pin 2

# Wi-Fi 连接函数
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(SSID, PASSWORD)
        while not wlan.isconnected():
            print("正在连接 Wi-Fi...")
            time.sleep(1)
    print("Wi-Fi 连接成功:", wlan.ifconfig())

# MQTT 连接函数
def connect_mqtt():
    global client
    client = MQTTClient(EMQX_CLIENT_ID, EMQX_SERVER, EMQX_PORT, keepalive=MQTT_KEEPALIVE)
    client.set_callback(sub_cb)
    try:
        client.connect()
        print("已连接至 EMQX 服务器")
        client.subscribe(EMQX_TOPIC_WATER)
        emqx_led.off()  # 连接成功后关闭 LED
    except Exception as e:
        print("MQTT 连接失败:", e)
        emqx_led.on()  # 连接失败时点亮 LED
        client = None
        time.sleep(5)

# MQTT 回调函数：处理水泵控制指令
def sub_cb(topic, msg):
    print((topic, msg))
    if msg == b"ON":
        relay.on()
        print("水泵已开启")
        global pump_start_time
        pump_start_time = time.time()
    elif msg == b"OFF":
        relay.off()
        print("水泵已关闭")

# 重启设备函数
def safe_reset():
    print("尝试重新启动设备...")
    time.sleep(5)
    reset()

# 初次连接 Wi-Fi 和 MQTT
connect_wifi()
connect_mqtt()

# 定义土壤湿度发布的间隔时间
moisture_publish_interval = 10  # 每隔 10 秒发布一次湿度数据
last_moisture_publish_time = time.time()
pump_start_time = None  # 用于记录水泵开启的时间

# 主循环：定期上传湿度数据和检测连接状态
while True:
    try:
        # 检查 Wi-Fi 连接状态
        wlan = network.WLAN(network.STA_IF)
        if not wlan.isconnected():
            print("Wi-Fi 断开，尝试重新连接...")
            connect_wifi()

        # 检查 MQTT 连接状态
        if client is None:
            print("MQTT 断开，尝试重新连接...")
            connect_mqtt()

        # 若 Wi-Fi 和 MQTT 均连接成功，执行数据上传和控制指令接收
        if client is not None and wlan.isconnected():
            # 每隔 10 秒发布一次土壤湿度数据
            current_time = time.time()
            if current_time - last_moisture_publish_time >= moisture_publish_interval:
                moisture_value = soil_sensor.read()
                print("当前土壤湿度:", moisture_value)
                client.publish(EMQX_TOPIC_MOISTURE, str(moisture_value))
                last_moisture_publish_time = current_time  # 更新上次发布时间
            
            # 检查是否有新的水泵控制指令
            client.check_msg()

            # 检查水泵运行时间，超过 1 分钟则自动关闭水泵
            if pump_start_time and (current_time - pump_start_time >= 60):
                relay.off()
                pump_start_time = None  # 重置时间
                print("水泵已自动关闭")

        # 若 MQTT 未连接，点亮 LED 指示灯
        if client is None:
            emqx_led.on()
        else:
            emqx_led.off()

    except Exception as e:
        print("运行时出现错误:", e)
        emqx_led.on()  # 出现异常时点亮 LED
        time.sleep(5)  # 若出错，等待 5 秒再重试
        client = None  # 清除当前 MQTT 客户端以触发重连
        # 如果错误次数过多，执行自动重启
        if time.time() - last_moisture_publish_time > 3600:  # 超过 1 小时未成功发布数据
            safe_reset()

    # 每隔 1 秒检查一次
    time.sleep(1)