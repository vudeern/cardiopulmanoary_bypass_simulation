"""Presentation aliases; never apply to frozen numerical/execution records."""
import re


def v1_display(text):
    text=re.sub(r'v2\.0-rc\.(\d+)',r'v1.15-dev.\1',text,flags=re.I)
    text=re.sub(r'(?<![A-Za-z0-9])rc\.(\d+)',r'v1.15-dev.\1',text,flags=re.I)
    text=text.replace('2.0.0rc5','1.15.0')
    text=text.replace('v1.14.0 is the latest published stable release and the final v1 snapshot','v1.14.0 is a superseded historical snapshot')
    text=text.replace('Final stable v1 remains v1.14.0','Final v1 is now v1.15.0').replace('Final stable v1 stays at v1.14.0','Final v1 is now v1.15.0')
    text=text.replace('Final v1 is v1.14.0','The earlier v1.14.0 snapshot is superseded by final v1.15.0')
    text=text.replace('final v1 remains v1.14.0','final v1 is v1.15.0')
    text=text.replace('Stable v2.0','The v1 MPC milestone').replace('stable v2.0','the v1 MPC milestone')
    text=text.replace('v2.0 status','V1 MPC target status').replace('v2.0 qualification','V1 MPC target qualification')
    text=text.replace('v2 evidence','v1 MPC target evidence').replace('v2.0 gates','v1 MPC target criteria')
    text=text.replace('V2.0 status','V1 MPC target status').replace('V2.0 remains','The v1 MPC target remains')
    return text.replace('/releases/tag/v1.14.0','/tree/v1.14.0')
