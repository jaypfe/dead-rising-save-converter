"""Serializer-derived field maps for DR2: Off the Record saves.

The story offset table contains only numeric field offsets derived from the
game's serializer behavior. It contains no save data, game assets, or code.
"""

from __future__ import annotations

import base64
import hashlib
import struct
import zlib


HEADER_LENGTH = 57
HEADER_U32_STARTS = (1, 5, 9, 13, 17, 21, 26, 32)
HEADER_SANDBOX_RANGE = (36, 57)

PLAYER_LENGTH = 0x811
_CORE_U32 = tuple(range(0x000, 0x028, 4))
_STAT_U32 = tuple(range(0x10C, 0x1B4, 4))
_STAT_COUNTER_U32 = (0x1B5,)
_TABLE_ID_U32 = tuple(0x1B9 + index * 8 for index in range(64))
_HASH_U32 = tuple(0x3B9 + index * 4 for index in range(14))
_TRACKER_U32 = tuple(
    0x3F1 + index * 8 + relative
    for index in range(100)
    for relative in (0, 4)
)
PLAYER_U32_STARTS = (
    _CORE_U32
    + _STAT_U32
    + _STAT_COUNTER_U32
    + _TABLE_ID_U32
    + _HASH_U32
    + _TRACKER_U32
)

STORY_END = 0x1A95E
STORY_U16_STARTS = (0x00C,)
_STORY_U32_COUNT = 8765
_STORY_U32_RAW_SHA256 = (
    "9580cee288e035499e0de88ccf03f0d9d89e0d8e4aae4694710a6157e9c1a6da"
)
_STORY_U32_PACKED_B85 = (
    "c-kc0e^gXu;`njE?bk*{Kg^<{)mB_-#f_4Zl8Oo|X{EKv#Kgj)#H7T+!o<YFS}`%3N=z&)+;GLh!otGB!b(cYW=$+iOe`u)O8kf`"
    "eqVdOf4t7|2#2}vd!Kvf&YhX(hJ}TN{ej~-nbSCvXkr*ZEOEq>KqASc@^@|}lWcOyr;uWv<~ho#q?%glY2<VMLo4lc(oHYNhFd1i"
    "B!*bxNhFz6{?4srl1(o86jIF7JV!Z|R8vbmjeO33Xr-M_y6NTE2#?R1#1Kn7b0}s$r35KsIj`^<)vV<sKH)RIAjEdQWfyz+kzd%)"
    "0S<A5@IGN-$8Z8CaVmW|oAc<;Kn62}ix|dmMsPLPaRXDC#zQ>9Eavb8PqBbSlu=Fvl~hqp4Ykx!PXmp7%IAE^f7rv1{K9??aEK#>"
    "8)(OH0w-}QeL0)+=+8g~GlYv6#&AY(HP>+iH*qro#xa3AxtqyMWf~9h2(y^O6FkKN77=6#%Xpbrd5zV)!CSn;dwjr0e8OjZL5S^q"
    "%P#itBfqep103QA;m7Fb1Ww{q`f@hs(Vu|~W(XHCjNy#nYOdo3ZsKMFjAH_KayOHi$}}G05oR%mCwPhlEF#Dfmhm#L@*1mogSU8x"
    "_xOO1_=L~+f)LyJmR;=OM}A>H2ROtL!jIL@37o{K^yO^Mqdx-~%n&YO7{eLC)m+C7+{DcU7{>(e<ZdQ2m1#W0Bg|qBPw*5ASVWK|"
    "EaPQf<uz9G25<2W@9_a2@d=;t1tGTcExXvmkNm=Z4seJggdeA$6F7-e>C4%iM}Gz~m?2!mForXNtGSLFxQUwyFpde_$=yt5D${s~"
    "N0`MNp5Q4Ku!tZ_SjNk|%4@9V4c_7%-s1y4;uAjO3qow?TXwOBANhs-9N-W~2=^p&3@30Br_z_RIgkDfWH3Xxh+zz81Xpt%H*ga-"
    "6JQ(@xRbk?%v7fF5RWj6IXuBrEMO5qmavSMd6m~#%^SSMJG{pSe8eYw#utRx&bRDh4?pq?`#HcNju3u=eoo*dPNgqra~}N}$Y6$W"
    "5yKeH2(IQjZr~<vCcro*a3^;&nW;?UAs%5Cb9jQMSimBJEMXZh^D3{gnm2fhcX*Ev_=r#Vj4ueWop0I29)9E(_H%$k93lLV`Z<A<"
    "IF-Jf&3W`^AcGmgMGRv&Be<IDxPhCvnE>OMz@6O9WTrBWhj@fp%;5>1VgZW?vV>*4%&WY{YTn>2-r+qy;3GcaGrl0icD`j7d-#!G"
    "*v|nDafI*_^>YFzaVmW|oAc<;Kn62}ix|dmMsPLPaRWDTGXcgifjhaI$xLM$5Ag`In8Oo1#R3))WC_c7nOAv@)x5!5yu*8Zz(;(-"
    "XM913?R?8F_V6RWu%81Q;t1i9`Z<A<xtuGxhLMb7G-DXccqTH5dzixgOlJl&nay10F`tDj=6RN~oE5BO6>C__I@Ys+jcj5wTiD7r"
    "cCeG(?Byr+@f!y@%u)KB6c%<ICvpm>(~omFp9>hog$(6lF6DBr<QhgYiqVW=EaO?hD%P-;b*yIt8`;EWwz7>K>|{54`H6k}#z78q"
    "ls-=OkK;s6;dJ_O4(D?LgSe2PT+F3h&XrulNJcT5F^pwA6Pd(4OyPc}GlQATW-jxX&q5aSJWE;53Rbd;HLPVF>)F6YHnEv4Y-Jle"
    "*vW48@)P^`?SIRDisfb`qZrK?#xkCXOkxW6Go2aCWHxh|$9xvDnCDr_a#paCRjgqx>sZeQHnNG$Y+)<g*uhSAvzMRP$8Q|uFh}VV"
    "Wt%aYv5aRTlemW|+|P7ou#wGdVJq9%!A^Fwm!G)wRNItm7|AF`GlsE@XCkXu%R1JxfsJfpGh5io`Cdd0;zEXUF_&^VS8@#_S<F(F"
    "vx1eZVhw9q$9j%C-5BL``f(2Da{+_6kfF?EF7uerLKgEpOIgke_HmHI9Hq}09)lA(h12QBB&Kjb)0x3cW;2(0%x4=r+09;lVjsV8"
    "ki#5hRA1|qv5aRTlemW|+|P7ovXRYfVJq9%!A^Fwm!G)Qi}fqHhLMb7G-DXccqX!nwX9=38`#JuHnWAToZrtn<wAyXF_&^VS8@#_"
    "S<F(Fvx1eZVhw9q$9j%C%R1$B`f(2Da{+_6kfF?EF7uerLKgEpOIgke_HmHI9Hr0M9)lA(h12QBB&Kjb)0x3cW;2(0%x4=r+09;l"
    "VjsV8ki#5hlnWwb7|VDjGKqVb!u?EV1Dn{)7PhjD9qeQ`d)db&=Y)k_#uZ$}wKVY+U-J#$@jXBAGr#gX|0UvF*C_ZSCvzHS5={&P"
    "h$W8una&JmGMnShv(7l3ew@SkT)-eMWGI(1f~&cX8@P#^2{4Wc+{xWkQB4iC)RE$1(vAF`e{d@qWRgWTIppy$kMbCg^CTsd@+>d#"
    "A}_IrANhs-9AMV@&U1K*1uP=S5|;5Yud<r8tYbYJ*vKX}vxTi}V+ViwQ&`xa`3ryLZ@kU>e8|T%(acwT%{P3<4|LK+H$C(c(cd=Y"
    "kDSbDoXL15GKqVb!fzbrD1BU*JB|}Mh12QBIb6VChHw$X7|sZ;<~nZRCT`|A$|$FTO5!hYosA@tNg<UR`8)sMRx-JZd%2GXc#wyA"
    "l*f3SCn@0zLTu+-b}{+S&Q*DcN0`MNp5Q4Ku!torX9X)+#TwSKj`eI{Bb$gE7#0@A8Jxwryu!bEoi}-#cX^)=`IsiYqJ>u4Xs3ft"
    "y6C2dULsr|9myz0GlsG3WG_FlkKZ`RVUE&gkZs5*^yO^Mqdx-~%n&YO7{eLC96sWNzu1N>BE;E)?T5U~9y;lwn;v?Ja3S|tB1tDe"
    "2IW*xNfp)9P)i;4G|)&BQ5RZfqRAwSY;wpYk9-O!q=;flXeLApF@JTOB9=JfNg$CVl1U+zG)f6lMk{T!(?KU)bkjpG5kvG6Njd>C"
    "D5ru-s;H)hTI#5$fkv8$a`C$_(PWZEHaX;yM?M7<QbaK&G!vqQn4x-!C60I!NF<45Qb;9@Qi7DxN*nET&`B5F^w3Mh-}DkmIsq~$"
    "r-DkVsHTQm>ZqrIMw*DaNH5W3l0`N-<dR1|1r$<5F(ot;qJ<c57z`kmIO0hlktC8yA(b>r2~tKYZM4%tCtY;YLoX2*>m`zO0%TB5"
    "1(j4$O%1iwQBMPnG!b=)UZTk)i)?bpC69axD5QvDN@ylT3o*m=5=$KMB#=lF$)u1<8l?m&qm?$=>7bJ?y6K^p2yea|OC;$8$e^4G"
    "DygEH8fvMdo(39eBI;7TM3YGt+2oK*9{ChdND;-9&`gLHVlLB5EOEq>Kq5&blR_$KloF(jR@!K%gHF2WriWf4hU+DgbOK~hP6d@z"
    "QB4iC)KO0ZjWiLJq?c$i$s(H^a>*l~0tzXjm=c-^(L&7SdWj{DcoIk?iDXhpC5=*ol+j8X?R3yd7v1#GOT-m=i6or>8I)5&B~?^Y"
    "LoIdG(?BClM2*l(G?`?PO%A!_kxv1I6j4kG&4g$n#v6SDh$W7A5=bP8WKu{ajZ%V?(MlWbbkIo`-Sp5)#Fcu9B%J^mlv6<^Ra8?$"
    "Ep^n>KqE~=U8R?3GRY#F9CFDcp8^UgqL>nz3DH8#)q05~j(8GCB#C5FNF|L@f|Sup8|`$^Nf+Jp&`U&$ULr{+KnCShP)QZl)KE(u"
    "^)%2(6H(XbC7MjK$R>we^2n!vLW(G+gl0mt5Ob|wVu>T31QJOinG{k<qm&?Jw9-a99dyz~H$C(cah+ZwNhd%C<y25f71h*GOC9wz"
    "&`1+e-fZqmG?`?PO%A!_kxv1I6j4kG&4g$nW~5$Xi6fo_5=kPN6jDi}lptla(ndQSbkapPJ@gWBy<Q?oCqM?}R8UD3)znZ+9rZNO"
    "NE1;v=p~v=vdAWfT=K}LfI^BWri5lfv=DQnUSf$Oo&*v}BAFCYNu!h?Wwg>pI~{b=MK?Y45;00Ik)#tKgK{dUq>5^4sHKj28fc`6"
    "s5HGqlSvlY<d91q`4mt{5yh0yOo$d@ZqiFEam15AB1t5ZLMmyL5~Pe)+GwYPPP*u(hh8Fl;Ne&zNhd%C<y25f71h*GOC9wz&`1+e"
    "qxBL^CRt>YLoRvbQ$Qg_6jMSoAzFw@*GnvM#FIcGNhFg(DruAwq>NVDXs3fty6C2dULtPROC;$8$e^4GDygEH8fvMdo(39eBI+M{"
    "i6)aQvdJNrJn|`^kRpmHp_vdZ#Ej8PEOEq>Kq5&blR_$KloF(jR@!K%gHF2WriWf4ZqZ95=>*82oC+$bqM90NsiU3-8fhXbpqFSe"
    "$s(H^a>*l~0tzXjm=c-^(L#(5*9;(*IO0hlktC8yA(b>r2~tKYZM4%tCtY;YLoX3y^%6-s0Wv73f=a5WriNPTsHcHOnuxkhFVSR@"
    "MK(F)l1DxT6jDSnB{UPFg_v=Ai6xGB5=bP8WKu{ajZ%V?(MlWbbkIo`-Sp5)M221>Nhd%C<y25f71h*GOC9wz&`1+e<Mk3vCRt>Y"
    "LoRvbQ$Qg_6jMSoAzFyJT`#f35l;e%B#}%CsiaX#kTP0nqn!>q>7tt+dWo2zmq^kHkU=>WR8mDXHPli^Jq<L{M3fJB^(C52vdAWf"
    "T=K}LfI^BWri5lfv=B2<FR{cCPXdV~kxUAyq)|$cGFoY)oenzbqMIIiiMT^Ak)#tKgK{dUq>5^4sHKj28fc`6s5|u%O(t1nlS3|f"
    "<WoQ)MHEv)Ga*`t$<j+Kam15AB1t5ZLMmyL5~Pe)+GwYPPP*u(hh8Ek=_QhM0%TB51(j4$O%1iwQBMPnG!b=|UZTk)i)?bpC69ax"
    "D5QvDN@ylT3o&==C6+kiNg$CVl1U+zG)f6lMk{T!(?KU)bkjpG5k6#iERm!WAcJx$sHBQ&YN(}-dKze?iKu(@5=|yqWRpWKdE`?-"
    "Aw?8ZLNg&+h`CoUvBVKi0*NG%ObV%_QA&_9T4|%54m#<gn;v?Jn5>sb(g~13ITch=MKv|lQb#=vG}1&=j$We4B#Ufv$R&?_3MizA"
    "VoGQxL<=!f^b$)P@g$H)63L{HN*bjEDWjD(+UcN^F1qQVmx%lH5=lA%GAO5lN~)-)hFa>Vr-4SAh?=UGXfnwnn;de<BcB2aDWaGX"
    "nhDWDj1RO9AeK1dNg$CVl1U+zG)f6lMk{T!(?KU)bkjpG5%=pQl5_%OP)-GvR8dV0wbW5h1C2Bh^?+WY$s~(xa>yl*d<rO}h+;};"
    "CPWJ{)ASNc9PuQOND|4UkV+b*1SzAHHrnZ+lP<dHp_hm}y+o2ufDFp1ppq)8siBrS>S>^nCZeY6C7MjK$R>we^2n!vLW(G+gl0mt"
    "5c8m3Vu>T31QJOinG{k<qm&?Jw9-a99dyz~H$C(c@sM63Nhd%C<y25f71h*GOC9wz&`1+eK2+V8Xfnwnn;de<BcB2aDWaGXnhDWD"
    "%nZH65=T4<B$7ljDWsA{DM89;rHytv=%kBodgvwMVZB6>PJj%`si2Z7s;QxtI_hblktU)Z(MvR$WRXn{x#W>g0fiJ%ObN||Xd$LR"
    "FR{cCPXdV~kxUAyq)|$cGFoY)oenzbqMIIiiI}OENYV+AK{*vvQbjd2)KW)14K&h3)T4TdCX+0($sw0K@+qK@B8n-YnGh|+%+gCN"
    "am15AB1t5ZLMmyL5~Pe)+GwYPPP*u(hh8Flu>V*hNhd%C<y25f71h*GOC9wz&`1+ev-J{9CRt>YLoRvbQ$Qg_6jMSoAzFxeOfRv-"
    "5l;e%B#}%CsiaX#kTP0nqn!>q>7tt+dWo2$mq^kHkU=>WR8mDXHPli^Jq<L{L{yPpqRAwSY;wpYk9-O!q=;flXeLApF?012OC0ee"
    "kVq2Aq>xG)r35LXl{VVxpp!1T>7kd1$Mq6PIsq~$r-DkVsHTQm>ZqrIMw*CvLNC!|l0`N-<dR1|1r$<5F(ot;qJ<b=A{js|am15A"
    "B1t5ZLMmyL5~Pe)+GwYPPP*u(hh8G)=_QhM0%TB51(j4$O%1iwQBMPnG!gZrUZTk)i)?bpC69axD5QvDN@ylT3o%dWC6+kiNg$CV"
    "l1U+zG)f6lMk{T!(?KU)bkjpG5&zUnB<TdmpqvUSsiK-1YN?~11{!H1YQA2g$s~(xa>yl*d<rO}h+;};CPWJ{C3=Y^j(8GCB#C5F"
    "NF|L@f|Sup8|`$^Nf+Jp&`ZPuy+o2ufDFp1ppq)8siBrS>S>^nCZc?isV~uFl0`N-<dR1|1r$<5F(ot;qJ@}+dWj{DcoIk?iDXhp"
    "C5=*ol+j8X?R3yd7v1#GOGK$&B1tDe2IW*xNfp)9P)i;4G|)&BQH%5vO(t1nlS3|f<WoQ)MHEv)Ga*`tc}6d>#1T&di6oIs3aO+~"
    "N{}*IX``JEI_aXD9(svbtd~gA36McK6;x71H8s>yM?DQR(nQp=dWj~JEV9WVmpt+*ppYVpDWRDVEyM)%5=$KMB#=lF$)u1<8l?m&"
    "qm?$=>7bJ?y6K^p2w$c<mPpbGkU=>WR8mDXHPli^Jq<L{MAY+oi6)aQvdJNrJn|`^kRpmHp_vdZ#Jr%FSmKB$fkcu>CWTbeC?!Z4"
    "t+dfj2c2}$O%J_9EYV9O=>*82oC+$bqM90NsiU3-8fhY`OfS)7l0`N-<dR1|1r$<5F(ot;qJ@~HdWj{DcoIk?iDXhpC5=*ol+j8X"
    "?R3yd7v1#GOT>$Mi6or>8I)5&B~?^YLoIdG(?BClL@m=xG?`?PO%A!_kxv1I6j4kG&4g$n#uqmS5KA2KB#=lF$)u1<8l?m&qm?$="
    ">7bJ?y6K^ph~;{TB%J^mlv6<^Ra8?$Ep^n>KqE~=y`-0DGRY#F9CFDcp8^UgqL>nz3DH8#%X*0=j(8GCB#C5FNF|L@f|Sup8|`$^"
    "Nf+Jp&`U&xULr{+KnCShP)QZl)KE(u^)%2(6HzPl5=|yqWRpWKdE`?-Aw?8ZLNg&+h<QaXvBVKi0*NG%ObV%_QA&_9T4|%54m#<g"
    "n;v?JcvUZvq!S>6aw@2#ifU@8rH*<UXrzfKUmosDG?`?PO%A!_kxv1I6j4kG&4g$nW~E+Yi6fo_5=kPN6jDi}lptla(ndQSbkapP"
    "J@gXsFTF&PPJj%`si2Z7s;QxtI_hblktU*E(@Qj&WRXn{x#W>g0fiJ%ObN||Xd$LbFR{cCPXdV~kxUAyq)|$cGFoY)oenzbqMIIi"
    "iCCqVNYV+AK{*vvQbjd2)KW)14K&h3)W7u-O(t1nlS3|f<WoQ)MHEv)Ga*`tS*@2?;)o}KM3P7*g;dfgB}f^qw9!rnopjMn54}YA"
    "0{gK<l1_jO%Bi4|DypfWmOAQbpphn`*61agOtQ!(hg|Z=r+`9=D5ivFLbMR`x?W<5Bc22jNg|mPQc0tfAZ4`DMmrsJ(nU8t^b+xg"
    "ULr{+KnCShP)QZl)KE(u^)%2(6HzsKi6)aQvdJNrJn|`^kRpmHp_vdZ#H`gzEOEq>Kq5&blR_$KloF(jR@!K%gHF2WriWf4-qcGZ"
    "=>*82oC+$bqM90NsiU3-8fhZxExkmONfz1UkV_u<6i`SJ#gx!Yh!$c@mN0-=;)o}KM3P7*g;dfgB}f^qw9!rnopjMn54}XJ(@P}j"
    "1jwMA3M#3hni^`Uqn-vDX(H-vy+o5q7TM&GOCI?YP)HHQl+a9w7GmDfODu83lRzR#B$GlaX_OMAj8@ucr-M$q=%$BWBI@)KNjd>C"
    "D5ru-s;H)hTI#5$fkv8$TCbOAGRY#F9CFDcp8^UgqL>nz3DH8#yLyQwj(8GCB#C5FNF|L@f|Sup8|`$^Nf+Jp&`ZR7dWj^R02!21"
    "K_yjGQ$sCv)YCvCO+=Znqc729l0`N-<dR1|1r$<5F(ot;qJ@|ZdWj{DcoIk?iDXhpC5=*ol+j8X?R3yd7v1#GOT_zni6or>8I)5&"
    "B~?^YLoIdG(?BClM17!_Xfnwnn;de<BcB2aDWaGXnhDWDOoLuxi6fo_5=kPN6jDi}lptla(ndQSbkapPJ@gW>Q7@6C6Ci_fDyXE2"
    "YHFyZj(Qqsq=~2x^%6}cS!9z#E_virKp{mGQ$jN#T8Q~bFR{cCPXdV~kxUAyq)|$cGFoY)oenzbqMIIii7;u*u|$$ifDFp1ppq)8"
    "siBrS>S>^nCZaa!C7MjK$R>we^2n!vLW(G+gl0mt5c9EKVu>T31QJOinG{k<qm&?Jw9-a99dyz~H$C(c@rhm{Nhd%C<y25f71h*G"
    "OC9wz&`1+epXw!=OtQ!(hg|Z=r+`9=D5ivFLbMRGSue4~5l;e%B#}%CsiaX#kTP0nqn!>q>7tt+dWmS#OC;$8$e^4GDygEH8fvMd"
    "o(39eBI+}}M3YGt+2oK*9{ChdND;-9&`gLHVoXppfLP*)CxJwgNG63;(kLZJ8LhO@P6wTI(M=D%L~PMZB<TdmpqvUSsiK-1YN?~1"
    "1{!H1s#!15WRgWTIpmT@J_Qs~L@^~a6QYHfFZ2>i9PuQOND|4UkV+b*1SzAHHrnZ+lP<dHp_hm+^%6-s0Wv73f=a5WriNPTsHcHO"
    "nuyw}muND{BAXm?$s?Zv3MrzP5}FCoLd;isi6xGB5=bP8WKu{ajZ%V?(MlWbbkIo`-Sp5)L`W}@q!S>6aw@2#ifU@8rH*<UXrzfK"
    "lVtTJnoP3DCWl<|$ftlpiYTUpW<s<OvrR9t#1T&di6oIs3aO+~N{}*IX``JEI_aXD9(sxRS}&2L6Ci_fDyXE2YHFyZj(Qqsq=~5Q"
    "dWj~JEV9WVmpt+*ppYVpDWRDVEyT3wC6+kiNg$CVl1U+zG)f6lMk{T!(?KU)bkjpG5j*q}Njd>CD5ru-s;H)hTI#5$fkv8$`bIC&"
    "WRgWTIpmT@J_Qs~L@^~a6QYHfZ}k#O9PuQOND|4UkV+b*1SzAHHrnZ+lP<dHp_d2~wH-?&=>*82oC+$bqM90NsiU3-8fhYGr(UAT"
    "B#Ufv$R&?_3MizAVoGQxL<=$B=_Qsp;z=NpB$7!Xl{88TQbsFnw9`Q+U3Ak!FA=-+5=lA%GAO5lN~)-)hFa>Vr-4SAh-%YIG?`?P"
    "O%A!_kxv1I6j4kG&4g$nX188qi6fo_5=kPN6jDi}lptla(ndQSbkapPJ@gXsy<Q?oCqM?}R8UD3)znZ+9rZNONE1<e^b$=bS!9z#"
    "E_virKp{mGQ$jN#T8J?z-~eKYBc22jNg|mPQc0tfAZ4`DMmrsJ(nU8t^b)aGFOj4ZAcJx$sHBQ&YN(}-dKze?iKrj+5=|yqWRpWK"
    "dE`?-Aw?8ZLNg&+i1|@3vBVKi0*NG%ObV%_QA&_9T4|%54m$abgB<24eLA!f#TlH%dGzNBu3|hBDWH%){^Yyq#4vzZhH^2NGLlh@"
    "<~DBU4j$k^9%c?t@D$5gK^^t%=K#n2>^sez#F<1BLp%v2awXR=lCg|uBKLA14^YfMDWjYUR<VY)Y-AIg`HHXkhM)PB-#J3~FP4dO"
    "IG>?h%%xn#wOmgoSxjdJl~nNsAs#lV<)b{tQ!HQ+uksqJsils3zT`i&u$#U7#8LX}^PO>`ID@nJD}Un>MsPLPF^&n`Ne;Q>QOrMi"
    "n&(-{a@Mkr^?b<3H1QqZ^8@=iz#&fh)f`szC58dSGK7mrA(gwhm-~30r7Wk7c6y1}Z$BiGC<bvM*ONvLxh!B2@A5vsu%EwlSr0tT"
    "Gd#z8e87<3EDyuDojdrMUpYef@8$wwA<J38N?zwp-sWSPXl6U#vWxv3;1Cf9H1J1KNM+yu*#|lKkhvWg$Y7F4W&(FImwCL#YPPVI"
    "103Sa9{U4Va1~i(^CTtQaoBq1`2Sjme8>0f<2QPVIAWd%`Z0(L8Omi`!BwPl3%7A6cQctsn8h6a$<sW;zxX%xH1HK)(?KUk2sfGQ"
    "G4$gc&L^G(63Hcx`7C5HOIXGSe8g9L%{LsS&r$mUmvbe5=O5h4Z00hL7kH7E*u@@x<ahp$|I#lkJnS6KCysa$NaaTU&QzxH7?1NL"
    "+t|TQP7Mza>&w|(%k|7+4zKejZ}TxtH1jRH*h3fH42=j6yO<PGxsg(y<ppY~qn;Uk!oy}Vo0oWnf3cnoY~%|<oc4$CurnFV5H8{t"
    "ZsT_D<vwOHhbMTNXLyb`d7F1>rHxU?golmhJHDr{3470G6r-8W3|6p`Eo@~Qzp$UV$AyQ@;{{&iUEZgYF1oq+`0%hxxtwdco;1cW"
    "fjh||mpmR}7E4*q3f|;xz97VQ_VF7FP6#&_qA~DCV}M7P#Vh=ab*yItJK4?H6T`#CGm*QQ%mNk>WEE?;ATm5`5Th8)7{)Pyr7UL!"
    "-|!vZbCAOv<&P(Yhn>u6T*F94aSOL`J9jggspL~YA@i8eLY||HZS45p-!!rEX`IOg4B|4b;9(x+d6u%Aw|Iy5*vd9`5POP!hIra&"
    "=d7skuydKi6FkLg-rz0X<$c0W4G%kpYq_36ig<w+d5zU{&`F=u!o!Z^EY2mF6ecs3XL*4QY@~xuju3vj$KpC}Ae$U=S->KKEM+-i"
    "XM~6SfoVKM3#|<9YyaU9X7LQq(Lf`gvYl@kZQ|-NOl2AmF_(EfM;Ya;WEE@pfuFgkUwGIso?-!uc#)TQh1I;lTdZdT!_Nv28^P6F"
    "PZ~MoGMl+9VHq#;4)5^+2ROu_v%|wKWGK^kh)1ZRni}5Y13qFiTiC%)b~7N_xZrV~<YivvHQwU`KH_t}<Uj0U4?l8{!yM(rbHc+;"
    ";dH*@Yrf%_bHl?<;3RJ3@BD+uc$_DBhUaLdjdr@}p_h}-vk!14{Taw$hBJZ}c#)S_%^Q476U|&~Qu0f=h1<BD8O&rh^)%2(Ghgu&"
    "`#AP|`!@X<$RzGz3e$Lqaw@3g-@HyEpVC7w5q}B~JDy1X!e6<T>&YgETpr|MKICJX=%AA>{!3VYW1EW@Mk+V*cOGFDbBG)e9u~zJ"
    "#1h9H+{L{-%47fg`33e>&gE}h!bnCjngHXN$!uO@HIaYz_lYB(3^K_gmpt;B#T-_!l2x2B&|`8g@g%T?t!!gAdx<ugd<+8^!PQJ;"
    "68A8bX}rLTyu>@a#|M1QmmD+5I3$rI#xkCX+{=ADz%pLuRo>)nwy>2S_?avI5*~IH*K#9&XCjlxr+`ALsHTPw_=sQmo&O_zu;t<e"
    "&gMM&6GuD=T+WqT!(H6V3}!N$fAMc#X9FAA#7S|^b?D2Byu=Q65_zHR#u+4%#3b&afkr+h#CHDnS7U-)@>oQWB`jwJ8`;EWcCm*Z"
    "dO2x`WuY&(l0hc-avu*cliAE=G0(G<S9y)qyv@73&)0lIe>WN!$R%9H6^vml<LRX9e?K4U=Ul;fCh{_`@){r0#L0hitl><CF`Rpt"
    "!u^y`N<9rUvYWm1y~uXtJd#M}7H;Eqma?1`yun+<BpBPoGK}GjU?iiso5@V2fI^BWp_FG?&I(piO$|*n^A)?;!;k#NK@M~5#g1*9"
    "Okd8Xfku8|Khc+1Mp8)SMka74cQch~{Ki2JbICC4nk%@0o0!d9=J6sgv4*v*<3m2Ci6ex&dBic?cd79~38gG&1uJ=zw|SSdE^{m)"
    "j(8Fn&qO9MnW?<an|#I>{9(A`GG}ove_|%HnM*0p@&d2&8mp<Jo(8tCm2G^_5B$s_ju4(?9djCIash+5kjuD&tGJ1q2~b8k6@0`e"
    "9Hr0Y&aJqDtGJeNOyE8q;6di_1W&PymwA;B_=vCgnr}El_!ZVSvzg00e&u(L8{zq#B$7#CCbOB#B7!VoIV*UV_c_R6PIDuWGa1NW"
    "hLA)uDU?vkvy@TJCw#_zSL)(H=3Zsln9mAU@)qy#9*um;=lsMzju3veK2GK|&g5b)<vMQQCT=BzOlC5h1uP;+ITcj0kxhiy&bPGF"
    "K_@4rIPP&i7chvwaS4|ZU>x@_h5LD!M|q6ptYACe{_p><@&7!|v%J8I)KbSMe8v}a)58hZS`JR-GOpk%CUFl_c$CL@oCPc*$V<G!"
    "zj%YUc!v#aWEXol$YD;n&SP;Z*Kq?kF@~|sXCaGO#TvTkriXYpib)`mLW<bLX11`69dyx653wWd^9*MMSMyJv<{6r3<^YE{{(8@U"
    "L~$8ca1{Z@F@bU_sN_xFriE5|=;fpvbkdgr#1hASJiu(`GLLd9sN`$D;XA@^bo}9X&Lo<@aS4}^LoRtd%40mvOT5Bv_VN=4In19%"
    "g@^r_n+Y(E`*?r{S;%7E<$XTnQ$DASb~-pF&GsagIBw&1?qCY{Go51oNsuMH&AWWdE`H^A{*Mti***jq$GzOg1I%I$Pf$q}-?EDz"
    "_?a`@MCdHeWh&E18toWD3S$_{c&0OhnFLwFGCtxHKI6P}=MM}djdbqg0p8*r!f&=NIDz4e;A-yWJ|18>D_BY180UZ#Fo!2-<}3b7"
    "*e$j>HPq5d8}0neubdUo$e)NMj&yF}HZsZLNlGZ?Im&3DkxyynD|+Z9!VQ>?Cz4CJj4MbXmHT*r2PvSCGRmpoOa8+z?B}epmXpi4"
    "f~)ukxBl<nw|Q=26r*{CfAMeDv7QZl%IAE^x9nmMopjO7QTmMYJj5BC#kmY*FhjVUE4hX=(z%5!vdLjOGnmPI7P6StyuoLDL5SNk"
    "jCJm!-+0%YIG=xTD;d1Ni@d}t*07dWZ+D)+YTo62K4c49*+x4Zbdo;7vT_@_<gtWhY-AIgIm}V|xQW(joJll;xR9abkxv10na6y}"
    "si2bAd6T#Kh)+1cA&&g-Z%y>KxR|TBmg@;HjtSh&WFF>G9{b<#-r;w-ojWL^n0I)OU-_Ls+-V#V$wVe`5BU_ZoE6kiOC3!#^A!WL"
    "Y<KQvG7s}8kFkJ71lh!9_V6R8OmcmK7zQwei)g*eKFAz5CVPTmlkMwVPZ~#atn(?h<y6~}ula@^dRcS7?ao!x^fSYa&1Ui+T4?1L"
    "_H%&D8O9~6d4q5Gjzb*b%!h4P{=uzeFqx@L<7HmuOa4O(-|;=?JYt-3E!R^*DTg^qp905Bk{QPY=ChEOc!fqjWe-2nLoa8~bj&24"
    "1a9JHvdCr;LEhjkn)!-7{KzqnI*u}s!Cc1;q;m_CnaYDa%v|R2G|#Y%ms!Oc*76STv5C!WA;flevzMRP&jF6oXO?3LCvht0a6T6>"
    "m?2!s<y^^i+`t&dGM+oRoBNs03}!Kh`7C5HOIXHAR<VY+c!!N_Vl!V5Vkf)V%YF`Uls;~hcN`~iDt$Sd7zPka97DO7OSzn@xR&cl"
    "<7NVkV**)ZlS3}knZZnE^EgjZLMcI(u#A_fq>5^4SjT!cu#t~xqM5JQ&bRDh4;^&UMK^~zN}t(!i6n|MIE(Y>&p-wfPXdV~aV6I<"
    "l2N2{3%7AQcXBtAnMxk{6i~=q<}sgzJj)Bb$V<G+YpmuCYN?~11~##oEo|j$zTrE*=SO~FKL_Zcmx#x_9_K_(;dJ_OE`Q?B{DmQ0"
    "#4v`FObV&o$Y{nemhs%dUEIrkOyeOQVHQOc^G}{;G0(G<<-Eeb_&2Zf7Vq#LAJE9Be9o6_V+T9g%@6#{ul&yc@n5{*7WM~@Cz5n-"
    ";WlpP4({S!?&AR-<Y6A=F&^hhN+{)7Uf@Mu;uZeIzj>WEd7F26pAY$%CYt$*ula`W_?{p5nP2&x|Kq=e6<L0cCz2@6;4IFiKLZ)e"
    "5H4aENhFg(DmU_X{=uzekVzKV<d91q`4mt{5ykwIr+J3wD5IPTDygEH8fvMdo(3BEl+XE+|Ik7!ZM4%tCtY;YLoX3?jaUB2$(+WS"
    "L=(dRVu>T31QJOinG_ls^|*CU;0ce-L^lKdp2_n(F4Ld1&YAU;$NZ;#lgRm=Yj}?6662IVFR)({??$3)xon{^N=m7HlC(vRvE2HM"
    "@yQ*F9e>Dq)-jyv%wQ(7nae!pvyjC+&r+7Nf|aad4QpA)dN#0;O>AZhTiM1AcCwqj{KP(f;~<AQN}r(PA187Or_+yfIG+m`#Dxsy"
    "VlL%!uH+g<GK$fRVJzdB$RzGz3imUe8O&rhbD76{7P6S<S;}%&u##1*VJ+)e&jvQKiOp<bE8Ez?PIj}GpV-H59ON)Z>EmXw$8jR3"
    "a60`shx56BL0rgCF6L4$=Sr?&B%>J37{)T5iA>@irf@&gnZZnEGnaYHXCaGuo~0~j1uI#_8rHIo^=x1xo7l`2wz7>K>|{54`H6k}"
    "#z78qls?bv=R{87boy})=W_vrxR9Y-%%xn;m0ZI}MlqT(jAc9%nZ!Lz;eMtwgPF``F7uerLKgEpOIgkeR<epUtYsbR*}z6Nv6(Gw"
    "Wg9!#$!_-Y6Z`m$gB<24eO}PdiJZde^y3`P=K=<CAw#*COSzmYxrUL9Vl-nI%XlU-iF=sB{Y+;DGnvg?<}sgzEarKZvYZvHWEE>z"
    "%R1JxfsJfpGh5ioHg>R+-R$Kj_VF7BIm}V|EYZ)2oWkk!;~dWC0tRs*L%EpCxPq&>jvKg%F^uJQ?%*!&C6_#AFq7HL<tY~M49`(U"
    "Ij`^<tEr)uI_mk5kNJ!*2(g`=?B)l4=2w2FhhF-W>EuLCp)b+IZ~=q3kf97?ILV}t%8jIR3*(r;o!re7?&m=s=20G_nE5Q^Szh2p"
    "UZRpJ*07d!tmgwh;!{57Oa8+*e8(Ps<QMjHkpB|4)axEj;3Q6^ALsBV{>)$aD+wfWIahKGBe{v2xs?nu$>Lt7GL3u+D5QudDPa*o"
    "mavQ!tmNOk&YQeVJq>JPGh5ioc3Np;FF&!5-#Ek(B3^VZz#lo8GdPR$=+8g~Gn9+Dj4QZ`Yq^opjNvwJ=ML^7hg_yJgPF|c37+C<"
    "p5Zylc!^hdjn%xtTde1OKI9WV;|oIUU?<=613&XC-SlvjKFf?#PUKYj5={&Ph~=+b#4wUbCWTbeNGHHJCU7VBFog$rkcWAcB8r*M"
    "LKgEp%c!7|Rjgqx>v)e3Xyj8q=S#lk8+NgWANhsfILLpO{r?-U|AFH<nbYaVx%`Pg^B3Yt;8HH<O0MAsZsH%@N(PzS#l1{r8V~UZ"
    "vw55+S->KKEMYk-_!s}?b>5_odN#6&&1@mWc3NqpoeqBG0Eg%$V!3h3ABo}&&gMM&Gmr}z$|YRJ6<kFsH!_+rjAcCkuc12riGq&f"
    "I4ssLxLC5f*0rv>iX|B(OG->EY*@_5QBl!ilO?uu-HeQk94?x-!iEhSZnq>sz4VqWZ$%D^l8lUu+O@92hLe(tC3DztVPQQ#Jb%D@"
    "-_Ks(TGp_Zb*yIt8)+uS7PhjD?d+hF1WCF{agdKV%;$W`*L=qh9Oopb7-xdBoZ~zfxVY0Bl0z;5f?UfD%;Odou#m+p<zDV%1uLnd"
    "ni^`UBSMsV8fc`6W@5C^N*nFO>7a`QNxDhVLoa>wGr%B2q{%SM2&0TK&IFT8G0hBFT^dU^Iph)`NQf|b<WoQ)MHEv)DP@#XK_yjG"
    "Q$sCvM2J#P1C2D%OpF#<X``Ju9dwZ(NjE8a=%tT-1{h?BG#Q2&VU#h(nP8GBrkNpYm;GduLoNY=gb0&IJ_Qs~L@_0lQbsuyR8mDX"
    "HPli^gedhi&`1-_#Au<FHrk2PK^F;<bd#coUi#=~fI)^xlVO+<Mj2zA2_~6hni;Zo+fOz*<PsoAh%kBNQ$Qg_6jMSeWt3AvC98=L"
    "<vCv9B{s2{*J!1UcH-=0H~ZMn0Y2ampKyeu9OGLu9OneT@;iTWhAF1G!0bJ`#T@2xIYB~%$zwjZv5-Y9;U1Q=f|WeN<2=bK*07d!"
    "tY-roX(q-Nwz7@w?4XkbNxDgKkdHac0D}yX=0|?!B&Ya;)12iT|L`9dCH$}CkjoWZ#Wh^dJPIh}4i>YNW!%pLR8mDXH9W=BJj1g*"
    "&x>s06<+0a-r!B*yv;85@-FZ3KE3qu8DH=f-|#&@F~TTgjB|#+_?v&3^^P_(hfBGPE4iBMxRIN=mD{<KySSS&%6X87c$6nt#cCo%"
    "si%RByv$}=Xr+yI-eM<v*vEbj@F9ozlp`GF7-=#b=LEm-8>g9Mit}7x_Fi|&CCnv2kPu;RVm=F4$Rd`ojODCgB@go$HPli^gedhi"
    "&`1-_#Au<FHrk2PK^F;<bd#coUi#=~fI)^xlVO+<Mj2zA2_~6hni;b8X%E@tkV}9dA;RR5PXUD#QA`P?lu=Fvl~hqp4Ykw}Axb?B"
    "G}1&fF<NM)jdtR6&_#kI-K6NDmp=L#V2~lwWEf_IQN|c&f=Q;BW`?Y!{bZ9vE&+ms2$M%X1r$<5F(s5zMmZH!Qblz#Yu5jd%>e-"
)

ITEM116_SIZE = 0x74
ITEM116_U32 = (
    0x44,
    0x4C,
    0x50,
    0x54,
    0x58,
    0x5C,
    0x60,
    0x64,
    0x68,
    0x6C,
)
ITEM116_PLATFORM_RANGES = (
    (0x40, 0x44),
    (0x48, 0x4C),
    (0x70, 0x74),
)
FIELD04_ITEM_STARTS = tuple(0xC3B + record * 0x198 + 0x124 for record in range(2))
FIELD2C_ITEM_STARTS = tuple(
    0x1007 + bank * (4 + 12 * ITEM116_SIZE) + 4 + record * ITEM116_SIZE
    for bank in range(2)
    for record in range(12)
)
FIELD30_ITEM_STARTS = tuple(0x1AF3 + record * 0x13B + 0x95 for record in range(10))
ITEM116_STARTS = FIELD04_ITEM_STARTS + FIELD2C_ITEM_STARTS + FIELD30_ITEM_STARTS


def _decode_story_u32_starts() -> tuple[int, ...]:
    compressed = base64.b85decode(_STORY_U32_PACKED_B85.encode("ascii"))
    raw = zlib.decompress(compressed)
    if hashlib.sha256(raw).hexdigest() != _STORY_U32_RAW_SHA256:
        raise RuntimeError("embedded story schema failed its integrity check")
    expected_size = _STORY_U32_COUNT * 4
    if len(raw) != expected_size:
        raise RuntimeError(
            f"embedded story schema has {len(raw)} bytes, expected {expected_size}"
        )
    starts = struct.unpack(f"<{_STORY_U32_COUNT}I", raw)
    if starts != tuple(sorted(set(starts))):
        raise RuntimeError("embedded story schema is not sorted and unique")
    if not starts or starts[-1] > STORY_END - 4:
        raise RuntimeError("embedded story schema contains an out-of-range field")
    return starts


STORY_U32_STARTS = _decode_story_u32_starts()


def schema_byte_sets(
    u32_starts: tuple[int, ...],
    u16_starts: tuple[int, ...],
    end: int,
) -> tuple[set[int], set[int]]:
    """Partition a payload into typed numeric and endian-neutral bytes."""

    numeric: set[int] = set()
    for offset in u32_starts:
        if not 0 <= offset <= end - 4:
            raise ValueError(f"u32 outside payload at 0x{offset:x}")
        field = set(range(offset, offset + 4))
        if numeric & field:
            raise ValueError(f"overlapping numeric field at 0x{offset:x}")
        numeric.update(field)
    for offset in u16_starts:
        if not 0 <= offset <= end - 2:
            raise ValueError(f"u16 outside payload at 0x{offset:x}")
        field = set(range(offset, offset + 2))
        if numeric & field:
            raise ValueError(f"overlapping numeric field at 0x{offset:x}")
        numeric.update(field)
    raw = set(range(end)) - numeric
    if numeric & raw or numeric | raw != set(range(end)):
        raise RuntimeError("schema does not partition the payload")
    return numeric, raw


def convert_numeric_endian(
    payload: bytes,
    u32_starts: tuple[int, ...],
    u16_starts: tuple[int, ...] = (),
) -> bytes:
    """Swap only typed numeric fields and retain every endian-neutral byte."""

    converted = bytearray(payload)
    for offset in u32_starts:
        converted[offset : offset + 4] = payload[offset : offset + 4][::-1]
    for offset in u16_starts:
        converted[offset : offset + 2] = payload[offset : offset + 2][::-1]
    return bytes(converted)


def convert_player_endian(payload: bytes) -> bytes:
    if len(payload) != PLAYER_LENGTH:
        raise ValueError(
            f"unexpected player payload length {len(payload)}; expected {PLAYER_LENGTH}"
        )
    return convert_numeric_endian(payload, PLAYER_U32_STARTS)


def convert_story_endian(payload: bytes) -> bytes:
    if len(payload) != STORY_END:
        raise ValueError(
            f"unexpected story payload length {len(payload)}; expected {STORY_END}"
        )
    return convert_numeric_endian(payload, STORY_U32_STARTS, STORY_U16_STARTS)


_story_numeric, _story_raw = schema_byte_sets(
    STORY_U32_STARTS,
    STORY_U16_STARTS,
    STORY_END,
)
if len(PLAYER_U32_STARTS) != 331:
    raise RuntimeError("unexpected player schema field count")
if len(_story_numeric) != 35062 or len(_story_raw) != 73832:
    raise RuntimeError("unexpected story schema coverage")
