import pytest

from thrive_chatbot import data

OLD_HEADER = "Link,Title,Authors,MainIdea,Problems,Solutions,THRIVE,Implement"


def csv(*rows: str, header: str = OLD_HEADER) -> str:
    return "\n".join([header, *rows]) + "\n"


def test_normalize_category_variants():
    assert data.normalize_category("Community&Social") == "Community & Social Connection"
    assert data.normalize_category("Community & Social") == "Community & Social Connection"
    assert data.normalize_category("Education (Case Studies, White Papers)") == "Education"
    assert data.normalize_category("economic stability") == "Economic Stability"
    assert data.normalize_category("Closed-Loop Referrals") == "Closed-Loop Referrals"  # unknown passes through
    assert data.normalize_category("") == ""


def test_split_categories_dedupes_and_normalizes():
    assert data.split_categories("Livability; Economic Stability; Livability") == ["Livability", "Economic Stability"]
    assert data.split_categories("-") == []


def test_basic_parse_and_missing_link_kept():
    arts = data.parse_csv_text(
        csv(
            "https://drive.google.com/file/d/abc,Senior Cohousing,AARP,Idea one,Isolation,Cohousing,Community&Social,Pilot it",
            ",No Link Article,Someone,Idea two,Problem,Solution,Healthcare,Do it",
        )
    )
    assert [a.title for a in arts] == ["Senior Cohousing", "No Link Article"]
    assert arts[0].categories == ["Community & Social Connection"]
    assert arts[1].link == ""  # kept, cited by title only


def test_empty_markers_become_empty_strings():
    (a,) = data.parse_csv_text(csv("http://x,T,-,Idea,N/A,-,Education,NA"))
    assert (a.authors, a.problems, a.solutions, a.implement) == ("", "", "", "")
    assert "Problems:" not in a.text


def test_placeholder_and_blank_title_rows_skipped():
    arts = data.parse_csv_text(
        csv("http://x,DO NOT DELETE THIS ROW - LO ORGANIZATION,,,,,,", ",,,,,,,", "http://y,Real,A,Idea,P,S,Education,I")
    )
    assert [a.title for a in arts] == ["Real"]


def test_duplicate_titles_merge_keeping_fuller_row_and_union_categories():
    arts = data.parse_csv_text(
        csv(
            "http://x,Same Title,A,Short,,,Healthcare,",
            ",Same Title,A,A much longer main idea,Longer problems,Sols,Livability,Imp",
        )
    )
    assert len(arts) == 1
    assert arts[0].main_idea == "A much longer main idea"
    assert arts[0].link == "http://x"
    assert set(arts[0].categories) == {"Healthcare", "Livability"}


def test_new_sheet_layout_with_band_row_and_renamed_columns():
    header = (
        "Link to Document in Drive,Title,Author(s),Summary,Issues Identified,Solutions Identified,Other,"
        "THRIVE area(s),How can the THRIVE working group operationalize this?,CFF Potential Partners (nonprofit search),Status"
    )
    band = "File Info,Article Information,,,,,,THRIVE things,,,Reviewer"
    arts = data.parse_csv_text(
        band + "\n" + header + "\nhttp://x,Title A,Auth,Sum,Iss,Sol,,Education,Operate it,Partner,Completed\n"
    )
    (a,) = arts
    assert (a.main_idea, a.problems, a.solutions, a.implement) == ("Sum", "Iss", "Sol", "Operate it")
    assert a.categories == ["Education"]


def test_unknown_extra_columns_are_ignored():
    arts = data.parse_csv_text(csv("http://x,T,A,Idea,P,S,Education,I,extra", header=OLD_HEADER + ",Brand New Column"))
    assert len(arts) == 1


def test_missing_required_column_gives_clear_error():
    with pytest.raises(data.SheetFormatError) as err:
        data.parse_csv_text("Link,Title,Authors,Foo,Bar,THRIVE\nx,y,z,1,2,Education\n")
    assert "main_idea" in str(err.value)


def test_content_hash_changes_with_text():
    (a,) = data.parse_csv_text(csv("http://x,T,A,Idea,P,S,Education,I"))
    (b,) = data.parse_csv_text(csv("http://x,T,A,Idea CHANGED,P,S,Education,I"))
    assert a.id == b.id and a.content_hash != b.content_hash
