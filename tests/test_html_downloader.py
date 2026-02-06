from echr_extractor.ECHR_html_downloader import get_full_text_from_html


def test_get_full_text_preserves_paragraphs_and_commas():
    html = """
    <html>
      <head>
        <style>.hidden {display:none;}</style>
        <script>var x = 1;</script>
      </head>
      <body>
        <p><span>First</span> <span>paragraph.</span></p>
        <ol>
          <li>Sub-header A</li>
          <li>Sub-header B</li>
        </ol>
        <p><span>Second,</span> <span>paragraph</span></p>
      </body>
    </html>
    """

    text = get_full_text_from_html(html)

    assert "First paragraph." in text
    assert "Second, paragraph" in text
    assert "Sub-header A" in text
    assert "Sub-header B" in text
    assert "," in text

    idx_first = text.find("First paragraph.")
    idx_sub = text.find("Sub-header A")
    idx_second = text.find("Second, paragraph")
    assert idx_first != -1
    assert idx_sub != -1
    assert idx_second != -1
    assert idx_first < idx_sub < idx_second
    assert "\n\n" in text[idx_first + len("First paragraph.") : idx_sub]
    assert "\n\n" in text[idx_sub + len("Sub-header A") : idx_second]


def test_get_full_text_hudoc_main_content_sample():
    html = """
    <div class="s800EAC49"><div>
      <p class="sFE10DC93"><span class="sBB9EE52A">&nbsp;</span></p>
      <p class="s5E1364CA"><span class="sBB9EE52A">THIRD SECTION</span></p>
      <p class="sF2E0A612"><span class="s29100277">CASE OF ISMAILAJ AND OTHERS v. ALBANIA</span></p>
      <p class="s34DFC730"><span class="sA36B60A1">(Application no. <a class="appNumberLink" href="/eng#{&quot;appno&quot;:[&quot;28873/22&quot;]}" target="_blank">28873/22</a>)</span></p>
      <p class="s339D85E6"><span class="sBB9EE52A">&nbsp;</span></p>
      <p class="s339D85E6"><span class="sBB9EE52A">JUDGMENT</span><br><span class="sBB9EE52A">&nbsp;</span></p>
      <div class="s780F5245">
        <p class="sE77B86B8"><span class="sBB9EE52A">Art 6 § 1 (criminal) • Lack of impartiality of the Supreme Court judge having previously examined the merits of closely related first-instance proceedings against two of the applicants</span></p>
        <p class="sEC28DD31"><span class="sBB9EE52A">Art 46 • Execution of judgment • Individual measures</span></p>
        <p class="sEB972D3E"><span class="sBB9EE52A">&nbsp;</span></p>
        <p class="s55E5497F"><a name="_Hlk158113039" class="bookmark"><span class="sBB9EE52A">Prepared by the Registry. Does not bind the Court.</span></a></p>
      </div>
      <p class="s339D85E6"><span class="sBB9EE52A">STRASBOURG</span></p>
      <p class="s59272B2C"><span class="sBB9EE52A">8 July 2025</span></p>
      <p class="s598389FB"><span class="sF5E1C6CF">FINAL</span></p>
      <p class="s598389FB"><span class="sE208486F">08/10/2025</span></p>
      <p class="s598389F8"><span class="sA36B60A1">This judgment has become final under Article 44 § 2 of the Convention. </span><br><span class="sA36B60A1">It may be subject to editorial revision.</span></p>
    </div><br class="s4ACA9207"><div>
      <p class="s10950C61"><span class="s29100277">In the case of Ismailaj and Others v. Albania,</span></p>
      <p class="s32563E28"><span class="sBB9EE52A">Peeter Roosma</span><span class="sA36B60A1">, President</span><span class="sBB9EE52A">,</span><br><span class="sBB9EE52A">Lətif Hüseynov,</span><br><span class="sBB9EE52A">Darian Pavli,</span></p>
      <ol type="I" class="s6B505E72"><li class="s28F0D84C"><span>The Circumstances of the case</span></li></ol>
      <ol start="2" type="I" class="s6B505E72"><li class="sDA7B489D"><span>First set of proceedings for the confiscation of assets</span></li></ol>
      <ol type="I" class="s6B505E72"><li class="s5C5C410E"><span>Second set of proceedings for the confiscation of assets</span><ol type="A" class="s743F3A55"><li class="s879C130D"><span>First-instance and appeal proceedings</span></li></ol></li></ol>
    </div><br class="s4ACA9207"><div>
      <p class="s5E1364CA"><span class="sBB9EE52A">APPENDIX</span></p>
      <p class="s39E5096F"><span class="sBB9EE52A">List of applicants</span></p>
      <div class="s6DB91820">
        <table cellspacing="0" cellpadding="0" class="s8BB62139">
          <tbody>
            <tr><td class="sBAADFE8C"><p class="s2EF62ED2"><span class="sBB9EE52A">1.</span></p></td><td class="sBAADFE8C"><p class="s2EF62ED2"><span class="sBB9EE52A">Kastriot ISMAILAJ</span></p></td></tr>
          </tbody>
        </table>
      </div>
    </div></div>
    """

    text = get_full_text_from_html(html)

    assert "THIRD SECTION" in text
    assert "CASE OF ISMAILAJ AND OTHERS v. ALBANIA" in text
    assert "Application no. 28873/22" in text
    assert "JUDGMENT" in text
    assert "Prepared by the Registry. Does not bind the Court." in text
    assert "STRASBOURG" in text
    assert "8 July 2025" in text
    assert "FINAL" in text
    assert "08/10/2025" in text
    assert "APPENDIX" in text
    assert "List of applicants" in text
    assert "Kastriot ISMAILAJ" in text

    assert "THIRD SECTION\n\nCASE OF ISMAILAJ AND OTHERS v. ALBANIA" in text
    assert "Second set of proceedings for the confiscation of assets\n\nFirst-instance and appeal proceedings" in text
    assert "This judgment has become final under Article 44 § 2 of the Convention.\nIt may be subject to editorial revision." in text
    assert "\nLətif Hüseynov," in text
