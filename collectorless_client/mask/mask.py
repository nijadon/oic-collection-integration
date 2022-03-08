import logging
import os
import re
import xml.etree.ElementTree as ET

import pkg_resources

logger: logging.Logger = logging.getLogger(__name__)
DATA_FOLDER: str = pkg_resources.resource_filename(__name__, "data")
RULEPACKAGEVERSION: str = "4.12"
RP_FOLDER = os.path.join(
    DATA_FOLDER, "CSPC_Collection_Rules-RP{}/RP".format(RULEPACKAGEVERSION)
)
CSPC_MASKING_FILE: str = os.path.join(RP_FOLDER, "masking_rules", "cspc_masking_rule.xml")


def get_text(tag_name: str, element: ET.Element, default: str = "") -> str:
    el = element.find(tag_name)
    if el is not None:
        res = el.text
        if res is not None:
            return res
    return default


def _convert_replace_to_python(replace: str) -> str:
    """
    convert the replacement pattern to a python compatible one
    """
    return re.sub(r"\$(\d)", r"\\\1", replace)


# this is the list of keywords that trigger a masking rule,
# it should be updated as lasking rules are updated.
security_keywords = [
    "secret",
    "user",
    "pass",
    "crypt",
    "key",
    "aaa",
    "auth",
    "cert",
    "cred",
    "snmp",
    "ftp",
    "chap",
    "subject",
]


class Masks:
    _regexes = None

    def __init__(self, cspc_masking_file: str = CSPC_MASKING_FILE) -> None:
        logger.debug("cspc_masking_file=%s", cspc_masking_file)
        self._cspc_masking_file = cspc_masking_file

    @property
    def regexes(self):
        """
        reads the masking file and stores the regular expressions
        """
        if self._regexes is None:
            self._regexes = []
            tree = ET.parse(self._cspc_masking_file)
            root = tree.getroot()
            mask_pattern_list = root.find("MaskPatternList")
            if mask_pattern_list is not None:
                for mask_pattern in mask_pattern_list.iter("MaskPattern"):
                    expression = get_text("Expression", mask_pattern, "empty")
                    replacement = get_text("Replacement", mask_pattern, "empty")
                    if replacement == "empty" or expression == "empty":
                        logger.error(
                            "replacement (%s) or expression (%s) is None! Skipping",
                            replacement,
                            expression,
                        )
                        continue
                    replacement = _convert_replace_to_python(replacement)
                    self._regexes.append((re.compile(expression), replacement))
        return self._regexes

    def apply(self, line: str) -> str:
        """
        for lines that contain a `security_keyword` apply each
        masking rule in turn until one matches and return the resulting
        line or the original line
        """
        if any(w in str.lower(line) for w in security_keywords):
            # this could be further optimized by grouping regexes
            # by security_keyword and only try those regex that
            # are part of the matching security_keyword.
            for exp, rep in self.regexes:
                (new_line, number_of_subs_made) = exp.subn(rep, line)
                if number_of_subs_made > 0:
                    return new_line
        return line


def mask_file(raw_cli: str, masks: Masks) -> str:
    """
    returns path to a copy of `file_path` with masking rules applied.
    """
    return "\n".join([masks.apply(x) for x in raw_cli.split("\n")])
