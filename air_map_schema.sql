IF OBJECT_ID(N'dbo.MauBanDoKhongKhi', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.MauBanDoKhongKhi (
        MaMau INT IDENTITY(1,1) PRIMARY KEY,
        MaViTri VARCHAR(64) NOT NULL,
        ViDo FLOAT NOT NULL,
        KinhDo FLOAT NOT NULL,
        ThoiGianLay DATETIME2 NOT NULL,
        ThoiGianNguon DATETIME2 NULL,
        US_AQI FLOAT NULL,
        PM25 FLOAT NULL,
        ChiTiet NVARCHAR(MAX) NOT NULL
    );
    CREATE INDEX IX_MauBanDoKK_ViTri_ThoiGian
        ON dbo.MauBanDoKhongKhi (MaViTri, ThoiGianLay DESC, MaMau DESC);
END;
