IF OBJECT_ID(N'dbo.DiaDiem', N'U') IS NULL
    CREATE TABLE dbo.DiaDiem (
        MaDiaDiem VARCHAR(64) PRIMARY KEY,
        Ten NVARCHAR(200) NOT NULL,
        Nhom NVARCHAR(120) NOT NULL,
        ViDo FLOAT NOT NULL,
        KinhDo FLOAT NOT NULL,
        ViDoTiengOn FLOAT NOT NULL,
        KinhDoTiengOn FLOAT NOT NULL,
        TenKhuVucTiengOn NVARCHAR(200) NOT NULL,
        ChiTiet NVARCHAR(MAX) NULL
    );
GO
IF COL_LENGTH('dbo.DiaDiem', 'ChiTiet') IS NULL
    ALTER TABLE dbo.DiaDiem ADD ChiTiet NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('dbo.NguonDL', 'MaDiaDiem') IS NULL
    ALTER TABLE dbo.NguonDL ADD MaDiaDiem VARCHAR(64) NULL;
IF COL_LENGTH('dbo.NguonDL', 'ChiTiet') IS NULL
    ALTER TABLE dbo.NguonDL ADD ChiTiet NVARCHAR(MAX) NULL;
GO
UPDATE dbo.NguonDL SET MaDiaDiem = 'hanoi'
WHERE MaDiaDiem IS NULL AND TenNguon = N'Open-Meteo Hà Nội';
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_NguonDL_DiaDiem_ThoiGian' AND object_id = OBJECT_ID('dbo.NguonDL'))
    CREATE INDEX IX_NguonDL_DiaDiem_ThoiGian ON dbo.NguonDL (MaDiaDiem, ThoiGian DESC, Manguon DESC);
