(function () {
  const NOC_TO_FLAG = {
    AFG: 'af', AHO: 'cw', ALB: 'al', ALG: 'dz', AND: 'ad', ANG: 'ao', ANT: 'ag', ARG: 'ar', ARM: 'am', ARU: 'aw',
    ASA: 'as', AUS: 'au', AUT: 'at', AZE: 'az', BAH: 'bs', BAN: 'bd', BAR: 'bb', BDI: 'bi', BEL: 'be', BEN: 'bj',
    BER: 'bm', BHU: 'bt', BIH: 'ba', BIZ: 'bz', BLR: 'by', BOL: 'bo', BOT: 'bw', BRA: 'br', BRN: 'bh', BRU: 'bn',
    BUL: 'bg', BUR: 'bf', CAF: 'cf', CAM: 'kh', CAN: 'ca', CAY: 'ky', CGO: 'cg', CHA: 'td', CHI: 'cl', CHN: 'cn',
    CIV: 'ci', CMR: 'cm', COD: 'cd', COK: 'ck', COL: 'co', COM: 'km', CPV: 'cv', CRC: 'cr', CRO: 'hr', CUB: 'cu',
    CYP: 'cy', CZE: 'cz', DEN: 'dk', DJI: 'dj', DMA: 'dm', DOM: 'do', ECU: 'ec', EGY: 'eg', ERI: 'er', ESA: 'sv',
    ESP: 'es', EST: 'ee', ETH: 'et', FIJ: 'fj', FIN: 'fi', FRA: 'fr', FSM: 'fm', GAB: 'ga', GAM: 'gm', GBR: 'gb',
    GBS: 'gw', GEO: 'ge', GEQ: 'gq', GER: 'de', DEU: 'de', GHA: 'gh', GRE: 'gr', GRN: 'gd', GUA: 'gt', GUI: 'gn',
    GUM: 'gu', GUY: 'gy', HAI: 'ht', HKG: 'hk', HON: 'hn', HUN: 'hu', INA: 'id', IND: 'in', IRI: 'ir', IRL: 'ie',
    IRQ: 'iq', ISL: 'is', ISR: 'il', ISV: 'vi', ITA: 'it', IVB: 'vg', JAM: 'jm', JOR: 'jo', JPN: 'jp', KAZ: 'kz',
    KEN: 'ke', KGZ: 'kg', KIR: 'ki', KOR: 'kr', KOS: 'xk', KSA: 'sa', KUW: 'kw', LAO: 'la', LAT: 'lv', LBA: 'ly',
    LBN: 'lb', LBR: 'lr', LCA: 'lc', LES: 'ls', LIE: 'li', LTU: 'lt', LUX: 'lu', MAD: 'mg', MAR: 'ma', MAS: 'my',
    MAW: 'mw', MDA: 'md', MDV: 'mv', MEX: 'mx', MGL: 'mn', MHL: 'mh', MKD: 'mk', MLI: 'ml', MLT: 'mt', MNE: 'me',
    MON: 'mc', MOZ: 'mz', MRI: 'mu', MTN: 'mr', MYA: 'mm', NAM: 'na', NCA: 'ni', NED: 'nl', NEP: 'np', NGR: 'ng',
    NIG: 'ne', NOR: 'no', NRU: 'nr', NZL: 'nz', OMA: 'om', PAK: 'pk', PAN: 'pa', PAR: 'py', PER: 'pe', PHI: 'ph',
    PLE: 'ps', PLW: 'pw', PNG: 'pg', POL: 'pl', POR: 'pt', PRK: 'kp', PUR: 'pr', QAT: 'qa', ROU: 'ro', RSA: 'za',
    RUS: 'ru', RWA: 'rw', SAM: 'ws', SEN: 'sn', SEY: 'sc', SGP: 'sg', SIN: 'sg', SKN: 'kn', SLE: 'sl', SLO: 'si',
    SMR: 'sm', SOL: 'sb', SOM: 'so', SRB: 'rs', SRI: 'lk', SSD: 'ss', STP: 'st', SUD: 'sd', SUI: 'ch', SUR: 'sr',
    SVK: 'sk', SWE: 'se', SWZ: 'sz', SYR: 'sy', TAN: 'tz', TGA: 'to', THA: 'th', TJK: 'tj', TKM: 'tm', TLS: 'tl',
    TOG: 'tg', TPE: 'tw', TTO: 'tt', TUN: 'tn', TUR: 'tr', TUV: 'tv', UAE: 'ae', UGA: 'ug', UKR: 'ua', URU: 'uy',
    USA: 'us', UZB: 'uz', VAN: 'vu', VEN: 've', VIE: 'vn', VIN: 'vc', YEM: 'ye', ZAM: 'zm', ZIM: 'zw',

    // Common historical/alternate codes.
    BAHAMAS: 'bs', CHINESE_TAIPEI: 'tw', FRG: 'de', GDR: 'de', HOL: 'nl', NBO: 'my', ROC: 'ru', SCG: 'rs', TCH: 'cz',
    URS: 'ru', YUG: 'rs', ZAI: 'cd',
  };

  window.NOC_TO_FLAG = NOC_TO_FLAG;
  window.nocToFlag = function nocToFlag(noc) {
    const code = String(noc || '').trim().toUpperCase();
    return NOC_TO_FLAG[code] || '';
  };
}());
