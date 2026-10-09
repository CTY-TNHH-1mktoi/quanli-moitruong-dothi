Create database
GiamsatMT;
go
use GiamsatMT;
CREATE TABLE NguonDL
(
    Manguon INT IDENTITY(1,1) PRIMARY KEY,
    TenNguon NVARCHAR(100) NOT NULL,
    ThoiGian DATETIME NOT NULL,
    PM25 DECIMAL(6,2),
    PM10 DECIMAL(6,2),
    NhietDo DECIMAL(5,2),
    DoAm DECIMAL(5,2),
    TiengOn DECIMAL(6,2)
);
CREATE TABLE CanhBao
(
    Macanhbao INT IDENTITY(1,1) PRIMARY KEY,
    Manguon INT NOT NULL,
    LoaiCanhBao NVARCHAR(100),
    MucDo NVARCHAR(50),
    NoiDung NVARCHAR(255),
    ThoiGian DATETIME NOT NULL,
    CONSTRAINT FK_CanhBao_NguonDL
    FOREIGN KEY (Manguon)
    REFERENCES NguonDL(Manguon)
);
CREATE TABLE PhanTichAI
(
    Maphantich INT IDENTITY(1,1) PRIMARY KEY,
    Manguon INT NOT NULL,
    KetQua NVARCHAR(100),
    NhanXet NVARCHAR(255),
    KhuyenNghi NVARCHAR(255),
    ThoiGian DATETIME NOT NULL,

    CONSTRAINT FK_PhanTichAI_NguonDL
    FOREIGN KEY (Manguon)
    REFERENCES NguonDL(Manguon)
);
