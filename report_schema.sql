IF OBJECT_ID(N'dbo.BaoCaoMT', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.BaoCaoMT (
        MaBaoCao INT IDENTITY(1,1) PRIMARY KEY,
        MaDiaDiem VARCHAR(64) NOT NULL DEFAULT 'hanoi',
        TieuDe NVARCHAR(200) NOT NULL,
        TuNgay DATETIME2 NOT NULL,
        DenNgay DATETIME2 NOT NULL,
        ThoiGianTao DATETIME2 NOT NULL,
        SoNgay INT NOT NULL,
        SoBanGhi INT NOT NULL,
        SoCanhBao INT NOT NULL,
        NoiDung NVARCHAR(MAX) NOT NULL
    );
    CREATE INDEX IX_BaoCaoMT_ThoiGianTao
        ON dbo.BaoCaoMT (ThoiGianTao DESC, MaBaoCao DESC);
END;
IF COL_LENGTH('dbo.BaoCaoMT', 'MaDiaDiem') IS NULL
    ALTER TABLE dbo.BaoCaoMT ADD MaDiaDiem VARCHAR(64) NOT NULL
        CONSTRAINT DF_BaoCaoMT_DiaDiem DEFAULT 'hanoi' WITH VALUES;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_BaoCaoMT_DiaDiem' AND object_id = OBJECT_ID('dbo.BaoCaoMT'))
    EXEC(N'CREATE INDEX IX_BaoCaoMT_DiaDiem ON dbo.BaoCaoMT (MaDiaDiem, ThoiGianTao DESC, MaBaoCao DESC)');
