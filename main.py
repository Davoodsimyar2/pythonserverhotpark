from flask import Flask, request, jsonify
import time

app = Flask(__name__)

# نگهداری آخرین داده هر ESP
# device_data[device_id][code] = آخرین دیتا برای هر کد
device_data = {}
# زمان آخرین آپدیت برای هر کد
device_timestamp = {}

# تعیین device_id بر اساس code (هر 1000 تا یک device)
def get_device_id(code):
    try:
        code = int(code)
        return code // 1000
    except:
        return None

@app.route("/data", methods=["POST"])
def receive_data():
    """
    دریافت داده از ESP
    دیتا باید شامل فیلد 'code' باشد
    """
    global device_data, device_timestamp
    data = request.json

    if not data or "code" not in data:
        return jsonify({"error": "missing 'code' field"}), 400

    code = int(data["code"])
    device_id = get_device_id(code)
    if device_id is None:
        return jsonify({"error": "invalid code"}), 400

    # ایجاد دیکشنری برای device_id اگر وجود ندارد
    if device_id not in device_data:
        device_data[device_id] = {}
        device_timestamp[device_id] = {}

    # ذخیره داده
    device_data[device_id][code] = data
    device_timestamp[device_id][code] = time.time()

    print(f"Device {device_id} code {code} updated:", data)
    return jsonify({"status": "success", "device_id": device_id, "code": code})


@app.route("/poll", methods=["GET"])
def poll():
    """
    GET endpoint:
    - ESP: ?device_id=0&last=timestamp → long-polling، دریافت همه کدهای رنج
    - موبایل: ?code=1234 → دریافت آخرین دیتا فقط برای یک کد مشخص
    """
    last = float(request.args.get("last", 0))
    get_time = time.time()  # زمان GET زدن

    # حالت موبایل: فقط یک کد مشخص
    code = request.args.get("code")
    if code is not None:
        try:
            code = int(code)
        except:
            return jsonify({"error": "invalid code", "get_timestamp": get_time}), 400
        device_id = get_device_id(code)
        if device_id in device_data and code in device_data[device_id]:
            return jsonify({
                "data": device_data[device_id][code],
                "timestamp": device_timestamp[device_id][code],  # زمان ذخیره دیتا
                "get_timestamp": get_time                        # زمان GET زدن
            })
        else:
            return jsonify({"status": "no data for this code", "get_timestamp": get_time}), 404

    # حالت ESP: دریافت همه کدهای رنج
    device_id = request.args.get("device_id")
    if device_id is None:
        return jsonify({"error": "device_id missing", "get_timestamp": get_time}), 400
    try:
        device_id = int(device_id)
    except:
        return jsonify({"error": "invalid device_id", "get_timestamp": get_time}), 400

    timeout = 30
    start = time.time()
    while time.time() - start < timeout:
        updated_codes = {}
        if device_id in device_timestamp:
            for code, ts in device_timestamp[device_id].items():
                if ts > last:
                    updated_codes[code] = device_data[device_id][code]

        if updated_codes:
            # آخرین timestamp از بین همه کدهای جدید
            latest_ts = max(device_timestamp[device_id][c] for c in updated_codes)
            return jsonify({
                "data": updated_codes,
                "timestamp": latest_ts,      # زمان ذخیره دیتا
                "get_timestamp": time.time() # زمان GET زدن
            })

        time.sleep(0.5)

    # بدون داده جدید
    return jsonify({
        "status": "no new data",
        "timestamp": last,
        "get_timestamp": time.time()  # زمان GET زدن وقتی داده جدید نبود
    })


@app.route("/", methods=["GET"])
def home():
    """نمایش همه ESPها برای دیباگ"""
    return jsonify({
        "devices": device_data,
        "timestamps": device_timestamp,
        "get_timestamp": time.time()  # زمان GET زدن برای دیباگ
    })


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)