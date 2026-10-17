"""EF file-identifier tables — extracted from the pinned specs.

``KNOWN_FIDS`` is the flat FID → name table used when no DF context is
known; ``DF_CHILDREN`` maps a DF (or the ADF of an AID-selected
application, keyed ``aid:<hex>``) to its child files/DFs; ``SFI_BY_DF``
maps an SFI to its FID within a DF (TS 102 221 §8.3: SFIs are unique only
within a DF).

Sources (PDFs in the workspace ``docs/uicc/``):
  * ETSI TS 102 221 V18.4.0 — MF files, Annex H.1 SFI list
  * 3GPP TS 31.102 V18.10.0 — ADF USIM files (4.2), the child DFs
    (4.3/4.4/4.6), the SFI annexes H.1–H.12, the Relay Node and
    certificate files (Annex L.6); Annex A/E were used as the ADF/DF file
    completeness cross-check
  * 3GPP TS 31.103 V18.3.0 — ADF ISIM files (4.2) and their per-file SFI
    rows (the spec has no SFI annex)
  * 3GPP TS 51.011 V4.15.0 — MF/DF_GSM/DF_TELECOM files (10.1–10.6)

A FID reused across DFs keeps its DF-specific name here (``4F09`` is
EF_SUPI_NAI under DF_5GS but EF_PROSE_GC under DF_ProSe; ``6F07`` is
EF_IMSI in the USIM/SIM but EF_IST in the ISIM; ``6F4E`` is EF_EXT4 in
DF_TELECOM but EF_EXT5 in the USIM ADF); only names that are identical in
every DF they occur in live in the flat table.

The tables are pinned by ``tests/data/spec_files.json`` (the extracted
tables) and ``tests/test_decode.py``; regenerate the fixture with
``tests/extract_spec_tables.py`` (`--check` re-verifies the tables
against the PDFs) when a spec revision is pinned.
"""

KNOWN_FIDS = {
    # ── Master File and common files (TS 102 221 Annex H; TS 51.011 10.1)
    '3f00': 'MF',
    '2f00': 'EF_DIR',
    '2f05': 'EF_PL',
    '2f06': 'EF_ARR',
    '2f07': 'EF_ENV-CLASSES',
    '2f08': 'EF_UMPC',
    '2fe2': 'EF_ICCID',

    # ── DF/ADF identifiers (TS 31.102 4.3/4.6; TS 51.011 10.2/10.4/10.6)
    # Children of the USIM ADF
    '5f3a': 'DF_PHONEBOOK',
    '5f3b': 'DF_GSM_ACCESS',       # TS 51.011 10.6: DF_MULTIMEDIA under DF_TELECOM
    '5f3c': 'DF_MexE',             # TS 51.011 10.6: DF_MMSS under DF_TELECOM
    '5f3d': 'DF_MCS',
    '5f3e': 'DF_V2X',
    '5f3f': 'DF_A2X',
    '5f40': 'DF_WLAN',
    '5f50': 'DF_HNB',              # TS 51.011 10.6: DF_GRAPHICS under DF_TELECOM
    '5f70': 'DF_SoLSA',
    '5f80': 'DF_BCAST',            # reserved for OMA BCAST (TS 31.102 4.3 note)
    '5f90': 'DF_ProSe',
    '5fa0': 'DF_ACDC',
    '5fb0': 'DF_TV',
    '5fc0': 'DF_5GS',
    '5fd0': 'DF_SAIP',
    '5fe0': 'DF_SNPN',
    '5ff0': 'DF_5G_ProSe',
    '5ff1': 'DF_5MBSUECONFIG',
    # Children of DF_GSM (SIM)
    '5f30': 'DF_IRIDIUM',
    '5f31': 'DF_GLOBALSTAR',
    '5f32': 'DF_ICO',
    '5f33': 'DF_ACES',
    '5f60': 'DF_CTS',
    # MF-level DFs
    '7f10': 'DF_TELECOM',
    '7f20': 'DF_GSM',

    # ── SIM DF_GSM / DF_TELECOM files (TS 51.011 10.3/10.5)
    '6f05': 'EF_LI',               # DF_GSM: EF_LP (TS 51.011 10.3.1)
    '6f07': 'EF_IMSI',             # ADF ISIM: EF_IST (TS 31.103 4.2.6)
    '6f20': 'EF_Kc',
    '6f2c': 'EF_DCK',
    '6f30': 'EF_PLMNsel',
    '6f31': 'EF_HPPLMN',
    '6f32': 'EF_CNL',
    '6f37': 'EF_ACMmax',
    '6f38': 'EF_UST',              # DF_GSM: EF_SST (TS 51.011 10.3.x)
    '6f39': 'EF_ACM',
    '6f3a': 'EF_ADN',
    '6f3b': 'EF_FDN',
    '6f3c': 'EF_SMS',
    '6f3d': 'EF_CCP',
    '6f3e': 'EF_GID1',
    '6f3f': 'EF_GID2',
    '6f40': 'EF_MSISDN',
    '6f41': 'EF_PUCT',
    '6f42': 'EF_SMSP',
    '6f43': 'EF_SMSS',
    '6f44': 'EF_LND',
    '6f45': 'EF_CBMI',
    '6f46': 'EF_SPN',
    '6f47': 'EF_SMSR',
    '6f48': 'EF_CBMID',
    '6f49': 'EF_SDN',
    '6f4a': 'EF_EXT1',
    '6f4b': 'EF_EXT2',
    '6f4c': 'EF_EXT3',
    '6f4d': 'EF_BDN',
    '6f4e': 'EF_EXT4',             # ADF USIM: EF_EXT5 (TS 31.102 4.2.37)
    '6f4f': 'EF_ECCP',             # ADF USIM: EF_CCP2 (TS 31.102 4.2.38)
    '6f50': 'EF_CBMIR',
    '6f51': 'EF_NIA',
    '6f52': 'EF_KcGPRS',
    '6f53': 'EF_LOCIGPRS',         # DF_TELECOM: EF_RMA (TS 31.102 4.5.8)
    '6f54': 'EF_SUME',
    '6f55': 'EF_EXT4',             # ADF USIM only (TS 31.102 4.2.45)
    '6f56': 'EF_EST',
    '6f57': 'EF_ACL',
    '6f58': 'EF_CMI',
    '6f5b': 'EF_START-HFN',
    '6f5c': 'EF_THRESHOLD',
    '6f60': 'EF_PLMNwAcT',
    '6f61': 'EF_OPLMNwAcT',
    '6f62': 'EF_HPLMNwAcT',
    '6f63': 'EF_CPBCCH',
    '6f64': 'EF_InvScan',
    '6f65': 'EF_RPLMNAcT',         # legacy (TS 31.102 4.2.45 NOTE 5)
    '6f73': 'EF_PSLOCI',
    '6f74': 'EF_BCCH',
    '6f78': 'EF_ACC',
    '6f7b': 'EF_FPLMN',
    '6f7e': 'EF_LOCI',
    '6fad': 'EF_AD',
    '6fae': 'EF_Phase',
    '6fb1': 'EF_VGCS',
    '6fb2': 'EF_VGCSS',
    '6fb3': 'EF_VBS',
    '6fb4': 'EF_VBSS',
    '6fb5': 'EF_eMLPP',
    '6fb6': 'EF_AAeM',             # TS 31.102 4.2.40: EFAaeM
    '6fb7': 'EF_ECC',
    '6fc5': 'EF_PNN',
    '6fc6': 'EF_OPL',
    '6fc7': 'EF_MBDN',
    '6fc9': 'EF_MBI',
    '6fca': 'EF_MWIS',
    '6fcb': 'EF_CFIS',
    '6fcd': 'EF_SPDI',
    '6fce': 'EF_MMSN',
    '6fd0': 'EF_MMSICP',
    '6fd1': 'EF_MMSUP',
    '6fd2': 'EF_MMSUCP',

    # ── ADF USIM files (TS 31.102 4.2; see DF_CHILDREN['7fff'])
    '6f01': 'EF_eAKA',
    '6f02': 'EF_IMPI',             # ADF USIM: EF_OCST (TS 31.102 4.2.81)
    '6f06': 'EF_ARR',
    '6f08': 'EF_Keys',
    '6f09': 'EF_KeysPS',           # ADF ISIM: EF_P-CSCF (TS 31.103 4.2.13)
    '6f0a': 'EF_AC_GBAUAPI',       # shared with ADF ISIM (TS 31.103 4.2.16)
    '6fc3': 'EF_Hiddenkey',
    '6fc4': 'EF_NETPAR',
    '6fc8': 'EF_EXT6',
    '6fcc': 'EF_EXT7',
    '6fcf': 'EF_EXT8',
    '6fd3': 'EF_NIA',
    '6fd4': 'EF_VGCSCA',
    '6fd5': 'EF_VBSCA',            # ADF ISIM: EF_GBABP (TS 31.103 4.2.21)
    '6fd6': 'EF_GBABP',
    '6fd7': 'EF_MSK',              # ADF ISIM: EF_GBANL (TS 31.103 4.2.22)
    '6fd8': 'EF_MUK',
    '6fd9': 'EF_EHPLMN',
    '6fda': 'EF_GBANL',
    '6fdb': 'EF_EHPLMNPI',
    '6fdc': 'EF_LRPLMNSI',
    '6fdd': 'EF_NAFKCA',
    '6fde': 'EF_SPNI',
    '6fdf': 'EF_PNNI',
    '6fe0': 'EF_ICE_DN',
    '6fe1': 'EF_ICE_FF',
    '6fe2': 'EF_NCP-IP',
    '6fe3': 'EF_EPSLOCI',
    '6fe4': 'EF_EPSNSC',
    '6fe5': 'EF_PSISMSC',
    '6fe6': 'EF_UFC',
    '6fe7': 'EF_UICCIARI',
    '6fe8': 'EF_NASCONFIG',
    '6fe9': 'EF_CERT',             # TS 31.102 Annex L.6.1.1
    '6fea': 'EF_eFRNid',           # TS 31.102 Annex L.6.2.1
    '6feb': 'EF_SCCmax',           # TS 31.102 Annex L.6.2.2
    '6fec': 'EF_PWS',
    '6fed': 'EF_FDNURI',
    '6fee': 'EF_BDNURI',
    '6fef': 'EF_SDNURI',
    '6ff0': 'EF_IAL',
    '6ff1': 'EF_IPS',
    '6ff2': 'EF_IPD',
    '6ff3': 'EF_ePDGId',
    '6ff4': 'EF_ePDGSelection',
    '6ff5': 'EF_ePDGIdEm',
    '6ff6': 'EF_ePDGSelectionEm',
    '6ff7': 'EF_FromPreferred',
    '6ff8': 'EF_IMSConfigData',
    '6ff9': 'EF_3GPPPSDATAOFF',
    '6ffa': 'EF_WebRTCURI',        # ADF USIM: EF_3GPPPSDATAOFFservicelist
    '6ffb': 'EF_TVCONFIG',
    '6ffc': 'EF_XCAPConfigData',
    '6ffd': 'EF_EARFCNList',
    '6ffe': 'EF_MuDMiDConfigData',

    # ── ADF ISIM files (TS 31.103 4.2; see DF_CHILDREN['aid:...'])
    '6f03': 'EF_DOMAIN',
    '6f04': 'EF_IMPU',
    '6f0b': 'EF_IMSDCI',
    '6fe7': 'EF_UICCIARI',
}

# DF/ADF children (child FID -> name), for context-aware SELECT-path
# resolution and DF-scoped file naming: the complete per-DF file tables
# of the pinned specs.  A FID reused across DFs (e.g. 4F01, 6F07)
# resolves against its parent; the flat KNOWN_FIDS above is the
# fallback for messages with no known DF context.
DF_CHILDREN = {
    '3f00': {  # MF (TS 102 221 Annex H; TS 51.011 10.1)
        '2f00': 'EF_DIR',
        '2f05': 'EF_PL',
        '2f06': 'EF_ARR',
        '2f07': 'EF_ENV-CLASSES',
        '2f08': 'EF_UMPC',
        '2fe2': 'EF_ICCID',
    },
    '7fff': {  # ADF USIM (TS 31.102 4.2; Annex L.6 for the RN/certificate files)
        '5f3a': 'DF_PHONEBOOK',
        '5f3b': 'DF_GSM_ACCESS',
        '5f3c': 'DF_MexE',
        '5f40': 'DF_WLAN',
        '5f50': 'DF_HNB',
        '5f70': 'DF_SoLSA',
        '5f80': 'DF_BCAST',
        '5f90': 'DF_ProSe',
        '5fa0': 'DF_ACDC',
        '5fb0': 'DF_TV',
        '5fc0': 'DF_5GS',
        '5fd0': 'DF_SAIP',
        '5fe0': 'DF_SNPN',
        '5ff0': 'DF_5G_ProSe',
        '5ff1': 'DF_5MBSUECONFIG',
        '6f01': 'EF_eAKA',
        '6f02': 'EF_OCST',
        '6f05': 'EF_LI',
        '6f06': 'EF_ARR',
        '6f07': 'EF_IMSI',
        '6f08': 'EF_Keys',
        '6f09': 'EF_KeysPS',
        '6f0a': 'EF_AC_GBAUAPI',
        '6f0b': 'EF_IMSDCI',
        '6f2c': 'EF_DCK',
        '6f31': 'EF_HPPLMN',
        '6f32': 'EF_CNL',
        '6f37': 'EF_ACMmax',
        '6f38': 'EF_UST',
        '6f39': 'EF_ACM',
        '6f3b': 'EF_FDN',
        '6f3c': 'EF_SMS',
        '6f3e': 'EF_GID1',
        '6f3f': 'EF_GID2',
        '6f40': 'EF_MSISDN',
        '6f41': 'EF_PUCT',
        '6f42': 'EF_SMSP',
        '6f43': 'EF_SMSS',
        '6f45': 'EF_CBMI',
        '6f46': 'EF_SPN',
        '6f47': 'EF_SMSR',
        '6f48': 'EF_CBMID',
        '6f49': 'EF_SDN',
        '6f4b': 'EF_EXT2',
        '6f4c': 'EF_EXT3',
        '6f4d': 'EF_BDN',
        '6f4e': 'EF_EXT5',
        '6f4f': 'EF_CCP2',
        '6f50': 'EF_CBMIR',
        '6f55': 'EF_EXT4',
        '6f56': 'EF_EST',
        '6f57': 'EF_ACL',
        '6f58': 'EF_CMI',
        '6f5b': 'EF_START-HFN',
        '6f5c': 'EF_THRESHOLD',
        '6f60': 'EF_PLMNwAcT',
        '6f61': 'EF_OPLMNwAcT',
        '6f62': 'EF_HPLMNwAcT',
        '6f73': 'EF_PSLOCI',
        '6f78': 'EF_ACC',
        '6f7b': 'EF_FPLMN',
        '6f7e': 'EF_LOCI',
        '6f80': 'EF_ICI',
        '6f81': 'EF_OCI',
        '6f82': 'EF_ICT',
        '6f83': 'EF_OCT',
        '6fad': 'EF_AD',
        '6fb1': 'EF_VGCS',
        '6fb2': 'EF_VGCSS',
        '6fb3': 'EF_VBS',
        '6fb4': 'EF_VBSS',
        '6fb5': 'EF_eMLPP',
        '6fb6': 'EF_AAeM',
        '6fb7': 'EF_ECC',
        '6fc3': 'EF_Hiddenkey',
        '6fc4': 'EF_NETPAR',
        '6fc5': 'EF_PNN',
        '6fc6': 'EF_OPL',
        '6fc7': 'EF_MBDN',
        '6fc8': 'EF_EXT6',
        '6fc9': 'EF_MBI',
        '6fca': 'EF_MWIS',
        '6fcb': 'EF_CFIS',
        '6fcc': 'EF_EXT7',
        '6fcd': 'EF_SPDI',
        '6fce': 'EF_MMSN',
        '6fcf': 'EF_EXT8',
        '6fd0': 'EF_MMSICP',
        '6fd1': 'EF_MMSUP',
        '6fd2': 'EF_MMSUCP',
        '6fd3': 'EF_NIA',
        '6fd4': 'EF_VGCSCA',
        '6fd5': 'EF_VBSCA',
        '6fd6': 'EF_GBABP',
        '6fd7': 'EF_MSK',
        '6fd8': 'EF_MUK',
        '6fd9': 'EF_EHPLMN',
        '6fda': 'EF_GBANL',
        '6fdb': 'EF_EHPLMNPI',
        '6fdc': 'EF_LRPLMNSI',
        '6fdd': 'EF_NAFKCA',
        '6fde': 'EF_SPNI',
        '6fdf': 'EF_PNNI',
        '6fe2': 'EF_NCP-IP',
        '6fe3': 'EF_EPSLOCI',
        '6fe4': 'EF_EPSNSC',
        '6fe6': 'EF_UFC',
        '6fe7': 'EF_UICCIARI',
        '6fe8': 'EF_NASCONFIG',
        '6fe9': 'EF_CERT',
        '6fea': 'EF_eFRNid',
        '6feb': 'EF_SCCmax',
        '6fec': 'EF_PWS',
        '6fed': 'EF_FDNURI',
        '6fee': 'EF_BDNURI',
        '6fef': 'EF_SDNURI',
        '6ff0': 'EF_IAL',
        '6ff1': 'EF_IPS',
        '6ff2': 'EF_IPD',
        '6ff3': 'EF_ePDGId',
        '6ff4': 'EF_ePDGSelection',
        '6ff5': 'EF_ePDGIdEm',
        '6ff6': 'EF_ePDGSelectionEm',
        '6ff7': 'EF_FromPreferred',
        '6ff8': 'EF_IMSConfigData',
        '6ff9': 'EF_3GPPPSDATAOFF',
        '6ffa': 'EF_3GPPPSDATAOFFservicelist',
        '6ffb': 'EF_TVCONFIG',
        '6ffc': 'EF_XCAPConfigData',
        '6ffd': 'EF_EARFCNList',
        '6ffe': 'EF_MuDMiDConfigData',
    },
    '7f10': {  # DF_TELECOM (TS 51.011 10.5; TS 31.102 4.5)
        '5f3a': 'DF_PHONEBOOK',
        '5f3b': 'DF_MULTIMEDIA',
        '5f3c': 'DF_MMSS',
        '5f3d': 'DF_MCS',
        '5f3e': 'DF_V2X',
        '5f3f': 'DF_A2X',
        '5f50': 'DF_GRAPHICS',
        '6f06': 'EF_ARR',
        '6f3a': 'EF_ADN',
        '6f3b': 'EF_FDN',
        '6f3c': 'EF_SMS',
        '6f3d': 'EF_CCP',
        '6f40': 'EF_MSISDN',
        '6f42': 'EF_SMSP',
        '6f43': 'EF_SMSS',
        '6f44': 'EF_LND',
        '6f47': 'EF_SMSR',
        '6f49': 'EF_SDN',
        '6f4a': 'EF_EXT1',
        '6f4b': 'EF_EXT2',
        '6f4c': 'EF_EXT3',
        '6f4d': 'EF_BDN',
        '6f4e': 'EF_EXT4',
        '6f4f': 'EF_ECCP',
        '6f53': 'EF_RMA',
        '6f54': 'EF_SUME',
        '6f58': 'EF_CMI',
        '6fe0': 'EF_ICE_DN',
        '6fe1': 'EF_ICE_FF',
        '6fe5': 'EF_PSISMSC',
    },
    '7f20': {  # DF_GSM (TS 51.011 10.3)
        '5f30': 'DF_IRIDIUM',
        '5f31': 'DF_GLOBALSTAR',
        '5f32': 'DF_ICO',
        '5f33': 'DF_ACES',
        '5f3c': 'DF_MexE',
        '5f60': 'DF_CTS',
        '5f70': 'DF_SoLSA',
        '6f05': 'EF_LP',
        '6f07': 'EF_IMSI',
        '6f20': 'EF_Kc',
        '6f2c': 'EF_DCKDe-personalizationControlKeys',
        '6f30': 'EF_PLMNsel',
        '6f31': 'EF_HPPLMN',
        '6f32': 'EF_CNL',
        '6f37': 'EF_ACMmax',
        '6f38': 'EF_SST',
        '6f39': 'EF_ACM',
        '6f3e': 'EF_GID1',
        '6f3f': 'EF_GID2',
        '6f41': 'EF_PUCT',
        '6f45': 'EF_CBMI',
        '6f46': 'EF_SPN',
        '6f48': 'EF_CBMID',
        '6f50': 'EF_CBMIR',
        '6f51': 'EF_NIA',
        '6f52': 'EF_KcGPRS',
        '6f53': 'EF_LOCIGPRS',
        '6f54': 'EF_SUME',
        '6f60': 'EF_PLMNwAcT',
        '6f61': 'EF_OPLMNwAcT',
        '6f62': 'EF_HPLMNwAcT',
        '6f63': 'EF_CPBCCH',
        '6f64': 'EF_InvScan',
        '6f74': 'EF_BCCH',
        '6f78': 'EF_ACC',
        '6f7b': 'EF_FPLMN',
        '6f7e': 'EF_LOCI',
        '6fad': 'EF_AD',
        '6fae': 'EF_Phase',
        '6fb1': 'EF_VGCS',
        '6fb2': 'EF_VGCSS',
        '6fb3': 'EF_VBS',
        '6fb4': 'EF_VBSS',
        '6fb5': 'EF_eMLPP',
        '6fb6': 'EF_AAeM',
        '6fb7': 'EF_ECC',
        '6fc5': 'EF_PNN',
        '6fc6': 'EF_OPL',
        '6fc7': 'EF_MBDN',
        '6fc8': 'EF_EXT6',
        '6fc9': 'EF_MBI',
        '6fca': 'EF_MWIS',
        '6fcb': 'EF_CFIS',
        '6fcc': 'EF_EXT7',
        '6fcd': 'EF_SPDI',
        '6fce': 'EF_MMSN',
        '6fcf': 'EF_EXT8',
        '6fd0': 'EF_MMSICP',
        '6fd1': 'EF_MMSUP',
        '6fd2': 'EF_MMSUCP',
    },
    '5f3a': {  # DF_PHONEBOOK (TS 31.102 4.4.2/4.6.2; EF_PBR assigns its files)
        '4f22': 'EF_PSC',
        '4f23': 'EF_CC',
        '4f24': 'EF_PUID',
        '4f30': 'EF_PBR',
    },
    '5f3b': {  # DF_GSM_ACCESS (TS 31.102 4.4.3) + DF_MULTIMEDIA (4.6.3)
        '4f20': 'EF_Kc',
        '4f47': 'EF_MML',
        '4f48': 'EF_MMDF',
        '4f52': 'EF_KcGPRS',
        '4f63': 'EF_CPBCCH',
        '4f64': 'EF_InvScan',
    },
    '5f3c': {  # DF_MexE (TS 31.102 4.4.4; TS 51.011 10.4.2)
        '4f40': 'EF_MexE-ST',
        '4f41': 'EF_ORPK',
        '4f42': 'EF_ARPK',
        '4f43': 'EF_TPRPK',
    },
    '5f3d': {  # DF_MCS (TS 31.102 4.6.4)
        '4f01': 'EF_MST',
        '4f02': 'EF_MCS_CONFIG',
    },
    '5f3e': {  # DF_V2X (TS 31.102 4.6.5)
        '4f01': 'EF_VST',
        '4f02': 'EF_V2X_CONFIG',
        '4f03': 'EF_V2XP_PC5',
        '4f04': 'EF_V2XP_Uu',
    },
    '5f3f': {  # DF_A2X (TS 31.102 4.6.6)
        '4f01': 'EF_AST',
        '4f02': 'EF_A2X_CONFIG',
        '4f03': 'EF_A2XP_PC5',
        '4f04': 'EF_A2X_DDAAP_PC5',
        '4f05': 'EF_A2X_DC2P_PC5',
        '4f06': 'EF_A2XP_Uu',
    },
    '5f40': {  # DF_WLAN (TS 31.102 4.4.5)
        '4f41': 'EF_Pseudo',
        '4f42': 'EF_UPLMNWLAN',
        '4f43': 'EF_OPLMNWLAN',
        '4f44': 'EF_UWSIDL',
        '4f45': 'EF_OWSIDL',
        '4f46': 'EF_WRI',
        '4f47': 'EF_HWSIDL',
        '4f48': 'EF_WEHPLMNPI',
        '4f49': 'EF_WHPI',
        '4f4a': 'EF_WLRPLMN',
        '4f4b': 'EF_HPLMNDAI',
    },
    '5f50': {  # DF_HNB (TS 31.102 4.4.6) + DF_GRAPHICS (4.6.1/TS 51.011 10.6.1)
        '4f20': 'EF_IMG',
        '4f21': 'EF_ICE_graphics',
        '4f81': 'EF_ACSGL',
        '4f82': 'EF_CSGT',
        '4f83': 'EF_HNBN',
        '4f84': 'EF_OCSGL',
        '4f85': 'EF_OCSGT',
        '4f86': 'EF_OHNBN',
    },
    '5f70': {  # DF_SoLSA (TS 31.102 4.4.1; TS 51.011 10.4.1)
        '4f30': 'EF_SAI',
        '4f31': 'EF_SLL',
    },
    '5f90': {  # DF_ProSe (TS 31.102 4.4.8)
        '4f01': 'EF_PROSE_MON',
        '4f02': 'EF_PROSE_ANN',
        '4f03': 'EF_PROSEFUNC',
        '4f04': 'EF_PROSE_RADIO_COM',
        '4f05': 'EF_PROSE_RADIO_MON',
        '4f06': 'EF_PROSE_RADIO_ANN',
        '4f07': 'EF_PROSE_POLICY',
        '4f08': 'EF_PROSE_PLMN',
        '4f09': 'EF_PROSE_GC',
        '4f10': 'EF_PST',
        '4f11': 'EF_PROSE_UIRC',
        '4f12': 'EF_PROSE_GM_DISCOVERY',
        '4f13': 'EF_PROSE_RELAY',
        '4f14': 'EF_PROSE_RELAY_DISCOVERY',
    },
    '5fa0': {  # DF_ACDC (TS 31.102 4.4.9)
        '4f01': 'EF_ACDC_LIST',
    },
    '5fc0': {  # DF_5GS (TS 31.102 4.4.11)
        '4f01': 'EF_5GS3GPPLOCI',
        '4f02': 'EF_5GSN3GPPLOCI',
        '4f03': 'EF_5GS3GPPNSC',
        '4f04': 'EF_5GSN3GPPNSC',
        '4f05': 'EF_5GAUTHKEYS',
        '4f06': 'EF_UAC_AIC',
        '4f07': 'EF_SUCI_Calc_Info',
        '4f08': 'EF_OPL5G',
        '4f09': 'EF_SUPI_NAI',
        '4f0a': 'EF_Routing_Indicator',
        '4f0b': 'EF_URSP',
        '4f0c': 'EF_TN3GPPSNN',
        '4f0d': 'EF_CAG',
        '4f0e': 'EF_SOR-CMCI',
        '4f0f': 'EF_DRI',
        '4f10': 'EF_5GSEDRX',
        '4f11': 'EF_5GNSWO_CONF',
        '4f15': 'EF_MCHPPLMN',
        '4f16': 'EF_KAUSF_DERIVATION',
    },
    '5fe0': {  # DF_SNPN (TS 31.102 4.4.12)
        '4f01': 'EF_PWS_SNPN',
        '4f02': 'EF_NID',
    },
    '5ff0': {  # DF_5G_ProSe (TS 31.102 4.4.13)
        '4f01': 'EF_5G_PROSE_ST',
        '4f02': 'EF_5G_PROSE_DD',
        '4f03': 'EF_5G_PROSE_DC',
        '4f04': 'EF_5G_PROSE_U2NRU',
        '4f05': 'EF_5G_PROSE_RU',
        '4f06': 'EF_5G_PROSE_UIR',
        '4f07': 'EF_5G_PROSE_U2URU',
        '4f08': 'EF_5G_PROSE_EU',
    },
    '5ff1': {  # DF_5MBSUECONFIG (TS 31.102 4.4.14)
        '4f01': 'EF_5MBSUECONFIG',
    },
    'aid:a0000000871004': {  # ADF ISIM, selected by AID (TS 31.103 4.2)
        '6f02': 'EF_IMPI',
        '6f03': 'EF_DOMAIN',
        '6f04': 'EF_IMPU',
        '6f06': 'EF_ARR',
        '6f07': 'EF_IST',
        '6f09': 'EF_P-CSCF',
        '6f0a': 'EF_AC_GBAUAPI',
        '6f0b': 'EF_IMSDCI',
        '6f3c': 'EF_SMS',
        '6f42': 'EF_SMSP',
        '6f43': 'EF_SMSS',
        '6f47': 'EF_SMSR',
        '6fad': 'EF_AD',
        '6fd5': 'EF_GBABP',
        '6fd7': 'EF_GBANL',
        '6fdd': 'EF_NAFKCA',
        '6fe5': 'EF_PSISMSC',
        '6fe7': 'EF_UICCIARI',
        '6ff7': 'EF_FromPreferred',
        '6ff8': 'EF_IMSConfigData',
        '6ffa': 'EF_WebRTCURI',
        '6ffc': 'EF_XCAPConfigData',
        '6ffe': 'EF_MuDMiDConfigData',
    },
}

# Short File Identifier (SFI) -> FID, scoped to the containing DF
# (TS 102 221 8.3: an SFI is only unique within a DF).  Sourced from
# the normative SFI annexes listed per DF; the ISIM annex does not
# exist, so its table is built from the SFI row of each file clause.
SFI_BY_DF = {
    '3f00': {  # MF (TS 102 221 Annex H.1)
        0x02: '2fe2',   # EF_ICCID
        0x05: '2f05',   # EF_PL
        0x06: '2f06',   # EF_ARR
        0x07: '2f07',   # EF_ENV-CLASSES
        0x08: '2f08',   # EF_UMPC
        0x1e: '2f00',   # EF_DIR
    },
    '7fff': {  # ADF USIM (TS 31.102 Annex H.1)
        0x01: '6fb7',   # EF_ECC
        0x02: '6f05',   # EF_LI
        0x03: '6fad',   # EF_AD
        0x04: '6f38',   # EF_UST
        0x05: '6f56',   # EF_EST
        0x06: '6f78',   # EF_ACC
        0x07: '6f07',   # EF_IMSI
        0x08: '6f08',   # EF_Keys
        0x09: '6f09',   # EF_KeysPS
        0x0a: '6f60',   # EF_PLMNwAcT
        0x0b: '6f7e',   # EF_LOCI
        0x0c: '6f73',   # EF_PSLOCI
        0x0d: '6f7b',   # EF_FPLMN
        0x0e: '6f48',   # EF_CBMID
        0x0f: '6f5b',   # EF_START-HFN
        0x10: '6f5c',   # EF_THRESHOLD
        0x11: '6f61',   # EF_OPLMNwAcT
        0x12: '6f31',   # EF_HPPLMN
        0x13: '6f62',   # EF_HPLMNwAcT
        0x14: '6f80',   # EF_ICI
        0x15: '6f81',   # EF_OCI
        0x16: '6f4f',   # EF_CCP2
        0x17: '6f06',   # EF_ARR
        0x18: '6fe4',   # EF_EPSNSC
        0x19: '6fc5',   # EF_PNN
        0x1a: '6fc6',   # EF_OPL
        0x1b: '6fcd',   # EF_SPDI
        0x1c: '6f39',   # EF_ACM
        0x1d: '6fd9',   # EF_EHPLMN
        0x1e: '6fe3',   # EF_EPSLOCI
    },
    '5f3b': {  # DF_GSM_ACCESS (TS 31.102 Annex H.2)
        0x01: '4f20',   # EF_Kc
        0x02: '4f52',   # EF_KcGPRS
    },
    '5f3d': {  # DF_MCS (TS 31.102 Annex H.7)
        0x01: '4f01',   # EF_MST
        0x02: '4f02',   # EF_MCS_CONFIG
    },
    '5f3e': {  # DF_V2X (TS 31.102 Annex H.8)
        0x01: '4f01',   # EF_VST
        0x02: '4f02',   # EF_V2X_CONFIG
        0x06: '4f03',   # EF_V2XP_PC5
        0x07: '4f04',   # EF_V2XP_Uu
    },
    '5f3f': {  # DF_A2X (TS 31.102 Annex H.12)
        0x01: '4f01',   # EF_AST
        0x02: '4f02',   # EF_A2X_CONFIG
        0x03: '4f03',   # EF_A2XP_PC5
        0x04: '4f04',   # EF_A2X_DDAAP_PC5
        0x05: '4f05',   # EF_A2X_DC2P_PC5
        0x06: '4f06',   # EF_A2XP_Uu
    },
    '5f40': {  # DF_WLAN (TS 31.102 Annex H.3)
        0x01: '4f41',   # EF_Pseudo
        0x02: '4f42',   # EF_UPLMNWLAN
        0x03: '4f43',   # EF_OPLMNWLAN
        0x04: '4f44',   # EF_UWSIDL
        0x05: '4f45',   # EF_OWSIDL
        0x06: '4f46',   # EF_WRI
        0x07: '4f47',   # EF_HWSIDL
        0x08: '4f48',   # EF_WEHPLMNPI
        0x09: '4f49',   # EF_WHPI
        0x0a: '4f4a',   # EF_WLRPLMN
        0x0b: '4f4b',   # EF_HPLMNDAI
    },
    '5f50': {  # DF_HNB (TS 31.102 Annex H.4)
        0x01: '4f81',   # EF_ACSGL
        0x02: '4f82',   # EF_CSGT
        0x03: '4f83',   # EF_HNBN
        0x04: '4f84',   # EF_OCSGL
        0x05: '4f85',   # EF_OCSGT
        0x06: '4f86',   # EF_OHNBN
    },
    '5f90': {  # DF_ProSe (TS 31.102 Annex H.5)
        0x01: '4f01',   # EF_PROSE_MON
        0x02: '4f02',   # EF_PROSE_ANN
        0x03: '4f03',   # EF_PROSEFUNC
        0x04: '4f04',   # EF_PROSE_RADIO_COM
        0x05: '4f05',   # EF_PROSE_RADIO_MON
        0x06: '4f06',   # EF_PROSE_RADIO_ANN
        0x07: '4f07',   # EF_PROSE_POLICY
        0x08: '4f08',   # EF_PROSE_PLMN
        0x09: '4f09',   # EF_PROSE_GC
        0x10: '4f10',   # EF_PST
        0x11: '4f11',   # EF_PROSE_UIRC
        0x12: '4f12',   # EF_PROSE_GM_DISCOVERY
        0x13: '4f13',   # EF_PROSE_RELAY
        0x14: '4f14',   # EF_PROSE_RELAY_DISCOVERY
    },
    '5fa0': {  # DF_ACDC (TS 31.102 Annex H.6)
        0x01: '4f01',   # EF_ACDC_LIST
    },
    '5fc0': {  # DF_5GS (TS 31.102 Annex H.9)
        0x01: '4f01',   # EF_5GS3GPPLOCI
        0x02: '4f02',   # EF_5GSN3GPPLOCI
        0x03: '4f03',   # EF_5GS3GPPNSC
        0x04: '4f04',   # EF_5GSN3GPPNSC
        0x05: '4f05',   # EF_5GAUTHKEYS
        0x06: '4f06',   # EF_UAC_AIC
        0x07: '4f07',   # EF_SUCI_Calc_Info
        0x08: '4f08',   # EF_OPL5G
        0x09: '4f09',   # EF_SUPI_NAI
        0x0a: '4f0a',   # EF_Routing_Indicator
        0x0b: '4f0b',   # EF_URSP
        0x0c: '4f0c',   # EF_TN3GPPSNN
        0x0d: '4f0d',   # EF_CAG
        0x0e: '4f0e',   # EF_SOR-CMCI
        0x0f: '4f0f',   # EF_DRI
        0x10: '4f10',   # EF_5GSEDRX
        0x11: '4f11',   # EF_5GNSWO_CONF
        0x15: '4f15',   # EF_MCHPPLMN
        0x16: '4f16',   # EF_KAUSF_DERIVATION
    },
    '5fe0': {  # DF_SNPN (TS 31.102 Annex H.11)
        0x01: '4f01',   # EF_PWS_SNPN
        0x02: '4f02',   # EF_NID
    },
    '5ff0': {  # DF_5G_ProSe (TS 31.102 Annex H.10)
        0x01: '4f01',   # EF_5G_PROSE_ST
        0x02: '4f02',   # EF_5G_PROSE_DD
        0x03: '4f03',   # EF_5G_PROSE_DC
        0x04: '4f04',   # EF_5G_PROSE_U2NRU
        0x05: '4f05',   # EF_5G_PROSE_RU
        0x06: '4f06',   # EF_5G_PROSE_UIR
        0x07: '4f07',   # EF_5G_PROSE_U2URU
        0x08: '4f08',   # EF_5G_PROSE_EU
    },
    'aid:a0000000871004': {  # ADF ISIM (TS 31.103: the SFI row of each file)
        0x02: '6f02',   # EF_IMPI
        0x03: '6fad',   # EF_AD
        0x04: '6f04',   # EF_IMPU
        0x05: '6f03',   # EF_DOMAIN
        0x06: '6f06',   # EF_ARR
        0x07: '6f07',   # EF_IST
    },
}
