#!/bin/bash
# Script to generate a local CA and a certificate for localhost

set -e

DIR="./certs"
mkdir -p $DIR

# 1. Generate Root CA
if [ ! -f "$DIR/rootCA.key" ]; then
    echo "Generating Root CA..."
    openssl genrsa -out $DIR/rootCA.key 4096
    openssl req -x509 -new -nodes -key $DIR/rootCA.key -sha256 -days 1024 -out $DIR/rootCA.pem \
        -subj "/C=VN/ST=Hanoi/L=Hanoi/O=DashResearch/CN=DashLocalCA"
fi

# 2. Generate Certificate for localhost
echo "Generating Certificate for localhost..."
openssl genrsa -out $DIR/localhost.key 2048

# Create config file for SAN (Subject Alternative Name)
cat > $DIR/localhost.ext << EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
IP.1 = 127.0.0.1
EOF

openssl req -new -key $DIR/localhost.key -out $DIR/localhost.csr \
    -subj "/C=VN/ST=Hanoi/L=Hanoi/O=DashResearch/CN=localhost"

openssl x509 -req -in $DIR/localhost.csr -CA $DIR/rootCA.pem -CAkey $DIR/rootCA.key \
    -CAcreateserial -out $DIR/localhost.crt -days 825 -sha256 -extfile $DIR/localhost.ext

echo "--------------------------------------------------------"
echo "Xong! Chứng chỉ đã được tạo trong thư mục $DIR"
echo "--------------------------------------------------------"
echo "ĐỂ TRÌNH DUYỆT (CHROME/EDGE) CHẤP NHẬN HTTP/3:"
echo "1. Bạn PHẢI thêm Root CA vào hệ thống (Trusted Root Certification Authorities)."
echo "   - File cần dùng: $DIR/rootCA.pem"
echo "2. Hướng dẫn nhanh cho Windows:"
echo "   - Nhấn đúp vào rootCA.pem -> 'Install Certificate' -> 'Local Machine'"
echo "   - Chọn 'Place all certificates in the following store' -> 'Trusted Root Certification Authorities'."
echo "3. Sau khi cài xong, hãy KHỞI ĐỘNG LẠI trình duyệt hoàn toàn."
echo "4. Nếu vẫn fallback về H2, hãy thử chạy Chrome với cờ sau để ép tin tưởng SPKI của cert:"
echo "   $(openssl x509 -in $DIR/localhost.crt -pubkey -noout | openssl pkey -pubin -outform der | openssl dgst -sha256 -binary | base64)"
echo "--------------------------------------------------------"
