import logging
import urllib.parse
from datetime import datetime
from enum import Enum
import re

logger = logging.getLogger("ANNOUNCEMENT")
debug = False


class Announcement:
    def __init__(self, title, url, category=None, date=None, indexer=None):
        self.title = title
        self.torrent_url = url
        self.category = category
        self.date = date
        self.indexer = indexer
        self.snatch_date = None

    def snatched(self):
        self.snatch_date = datetime.now()


def create_announcement(tracker, variables):
    for line_match in tracker.config.line_matched:
        line_match.process(tracker.config, variables)

    _insert_ssl_url(variables)

    torrent_url_var = "torrentSslUrl" if tracker.config.torrent_https else "torrentUrl"
    if not variables.get("torrentName"):
        logger.warning("Missing torrent name")
        return None
    elif not variables.get(torrent_url_var):
        logger.warning("Missing torrent URL")
        return None

    return Announcement(
        variables["torrentName"],
        variables[torrent_url_var],
        variables.get("category"),
        date=datetime.now(),
        indexer=tracker.config.short_name,
    )


def _insert_ssl_url(variables):
    if variables.get("torrentUrl") and not variables.get("torrentSslUrl"):
        variables["torrentSslUrl"] = re.sub("^https?", "https", variables["torrentUrl"])


class Var:
    def __init__(self, var_name, elements):
        self.var_name = var_name
        self.elements = []
        for element in elements:
            self.elements.append(Var.Element(element.tag, element.attrib))

    def process(self, tracker_config, variables):
        var = ""
        for element in self.elements:
            var_shard = None
            if element.var_type is self.Element.Type.STRING:
                var_shard = element.name
            else:
                if element.name in variables:
                    var_shard = variables[element.name]
                else:
                    var_shard = tracker_config.setting(element.name)

                if element.var_type is self.Element.Type.VARENC:
                    var_shard = urllib.parse.quote_plus(var_shard)

            if not var_shard:
                logger.warning(
                    "Could not build var '%s', missing variable '%s'",
                    self.var_name,
                    element.name,
                )
                return

            var = var + var_shard

        if debug:
            logger.debug("Setting variable: %s = %s", self.var_name, var)
        variables[self.var_name] = var

    class Element:
        class Type(Enum):
            STRING = 1
            VAR = 2
            VARENC = 3

        type_to_name = {Type.STRING: "value", Type.VAR: "name", Type.VARENC: "name"}

        def __init__(self, var_type, var):
            self.var_type = self.Type[var_type.upper()]
            self.name = var[self.type_to_name[self.var_type]]


class Http:
    def process(self, tracker_config, variables):
        logger.warning(
            "HTTP header (e.g. cookie) in tracker configuration not supported. "
            + "This might cause problems downloading the torrent file."
        )


class Extract:
    def __init__(self, srcvar, regex, groups, optional):
        self.srcvar = srcvar
        self.regex = regex
        self.groups = groups
        self.optional = optional

    # Returns None when no match was found
    def process_string(self, string):
        matches = re.search(self.regex, string)
        if matches:
            match_groups = {}
            for j, group_name in enumerate(self.groups, start=1):
                # Filter out missing non-capturing groups
                match = matches.group(j)
                if match is not None and not match.isspace():
                    match_groups[group_name] = match.strip()
            return match_groups

        return None

    def get_extract_variables(self, variables):
        match_groups = None
        if self.srcvar in variables:
            match_groups = self.process_string(variables[self.srcvar])
        return match_groups

    def process(self, tracker_config, variables):
        match_groups = self.get_extract_variables(variables)

        if match_groups is not None:
            if debug:
                for k in match_groups:
                    logger.debug("Setting variable: %s = %s", k, match_groups[k])
            variables.update(match_groups)
        elif not self.optional:
            logger.warning(
                "Extract: Variable '%s' did not match regex '%s'",
                self.srcvar,
                self.regex,
            )


class ExtractOne:
    def __init__(self, extracts):
        self.extracts = extracts

    def process(self, tracker_config, variables):
        for extract in self.extracts:
            extract_vars = extract.get_extract_variables(variables)
            if extract_vars is not None:
                if debug:
                    for k in extract_vars:
                        logger.debug("Setting variable: %s = %s", k, extract_vars[k])
                variables.update(extract_vars)
                return

        logger.warning("ExtractOne: No matching regex found")


class ExtractTags:
    def __init__(self, srcvar, split, setvarifs):
        self.srcvar = srcvar
        self.split = split
        self.setvarifs = setvarifs

    def process(self, tracker_config, variables):
        if self.srcvar not in variables:
            logger.warning(
                "ExtractTags: Could not extract tags, variable '%s' not found",
                self.srcvar,
            )
            return

        for tag_name in [
            x.strip() for x in re.split(self.split, variables[self.srcvar])
        ]:
            if not tag_name:
                continue

            for setvarif in self.setvarifs:
                new_value = setvarif.get_value(tag_name)
                if new_value is not None:
                    if debug:
                        logger.debug(
                            "Setting variable: %s = %s", setvarif.var_name, new_value
                        )
                    variables[setvarif.var_name] = new_value
                    break

    class SetVarIf:
        def __init__(self, var_name, regex, value, new_value):
            self.var_name = var_name
            self.regex = regex
            self.value = value
            self.new_value = new_value

        def get_value(self, tag_name):
            if (self.value is not None and self.value.lower() != tag_name.lower()) or (
                self.regex is not None and re.search(self.regex, tag_name) is None
            ):
                return None

            return self.new_value if self.new_value is not None else tag_name


class VarReplace:
    def __init__(self, name, srcvar, regex, replace):
        self.name = name
        self.srcvar = srcvar
        self.regex = regex
        self.replace = replace

    def process(self, tracker_config, variables):
        if self.srcvar not in variables:
            logger.warning(
                "VarReplace: Could not replace, variable '%s' not found", self.srcvar
            )
            return

        if debug:
            logger.debug(
                "Setting variable: %s = %s",
                self.name,
                re.sub(self.regex, self.replace, variables[self.srcvar]),
            )
        variables[self.name] = re.sub(self.regex, self.replace, variables[self.srcvar])


class SetRegex:
    def __init__(self, srcvar, regex, var_name, new_value):
        self.srcvar = srcvar
        self.regex = regex
        self.var_name = var_name
        self.new_value = new_value

    def process(self, tracker_config, variables):
        if self.srcvar not in variables:
            logger.warning(
                "SetRegex: Could not set variable, '%s' not found", self.srcvar
            )
            return

        if re.search(self.regex, variables[self.srcvar]):
            if debug:
                logger.debug("Setting variable: %s = %s", self.var_name, self.new_value)
            variables[self.var_name] = self.new_value


class If:
    def __init__(self, srcvar, regex, line_matches):
        self.srcvar = srcvar
        self.regex = regex
        self.line_matches = line_matches

    def process(self, tracker_config, variables):
        if self.srcvar not in variables:
            logger.warning(
                "If: Could not check condition, variable '%s' not found", self.srcvar
            )
            return

        if re.search(self.regex, variables[self.srcvar]):
            for matched in self.line_matches:
                matched.process(tracker_config, variables)
