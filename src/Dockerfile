FROM python:3.11

WORKDIR /app/src

# Sao chép requirements.txt và cài đặt thư viện cần thiết
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ nội dung của thư mục hiện tại vào thư mục /app trong container
COPY . .

# Kiểm tra file start.sh có tồn tại hay không và quyền truy cập
RUN ls -l /app/src

# Cấp quyền thực thi cho file start.sh
RUN chmod +x /app/src/start.sh

# Chạy file start.sh khi container khởi động
# CMD ["/app/src/start.sh"]
