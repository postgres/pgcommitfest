function verify_reject() {
    return confirm(
        'Are you sure you want to close this patch as Rejected?\n\nThis should only be done when a patch will never be applied - if more work is needed, it should instead be set to "Returned with Feedback" or "Moved to next CF".\n\nSo - are you sure?',
    );
}
function verify_withdrawn() {
    return confirm(
        "Are you sure you want to close this patch as Withdrawn?\n\nThis should only be done when the author voluntarily withdraws the patch.\n\nSo - are you sure?",
    );
}
function verify_returned() {
    return confirm(
        'Are you sure you want to close this patch as Returned with Feedback?\n\nThis should be done if the patch is expected to be finished at some future time, but not necessarily in the next commitfest. If work is undergoing and expected in the next commitfest, it should instead be set to "Moved to next CF".\n\nSo - are you sure?',
    );
}
function verify_next() {
    return confirm(
        'Are you sure you want to move this patch to the next commitfest?\n\nThis means the patch will be marked as closed in this commitfest, but will automatically be moved to the next one. If no further work is expected on this patch, it should be closed with "Rejected" or "Returned with Feedback" instead.\n\nSo - are you sure?',
    );
}
function findLatestThreads() {
    $("#attachThreadListWrap").addClass("loading");
    $("#attachThreadSearchButton").addClass("disabled");
    $.get("/ajax/getThreads/", {
        s: $("#attachThreadSearchField").val(),
        a: $("#attachThreadAttachOnly").val(),
    })
        .success((data) => {
            sel = $("#attachThreadList");
            sel.find("option").remove();
            $.each(data, (m, i) => {
                sel.append(
                    $("<option/>")
                        .text(`${i.from}: ${i.subj} (${i.date})`)
                        .data("subject", i.subj)
                        .val(i.msgid),
                );
            });
        })
        .always(() => {
            $("#attachThreadListWrap").removeClass("loading");
            $("#attachThreadSearchButton").removeClass("disabled");
            attachThreadChanged();
        });
    return false;
}

function browseThreads(attachfunc, closefunc) {
    $("#attachThreadList").find("option").remove();
    $("#attachThreadMessageId").val("");
    $("#attachModal").off("hidden.bs.modal");
    $("#attachModal").on("hidden.bs.modal", (e) => {
        if (closefunc) closefunc();
    });
    $("#attachModal").modal();
    findLatestThreads();

    $("#doAttachThreadButton").unbind("click");
    $("#doAttachThreadButton").click(() => {
        let subject = "";
        msgid = $("#attachThreadMessageId").val();
        if (!msgid || msgid === "") {
            msgid = $("#attachThreadList").val();
            if (!msgid) return;
            subject = $("#attachThreadList option:selected").data("subject");
            subject = subject.replace(/\bre: /gi, "");
            subject = subject.replace(/\bfwd: /gi, "");
            // Strips [PATCH], [POC], etc. prefixes
            subject = subject.replace(/\[\w+\]: /gi, "");
            subject = subject.replace(/\[\w+\] /gi, "");
        }

        $("#attachThreadListWrap").addClass("loading");
        $("#attachThreadSearchButton").addClass("disabled");
        $("#attachThreadButton").addClass("disabled");
        if (attachfunc(msgid, subject)) {
            $("#attachModal").modal("hide");
        }
        $("#attachThreadListWrap").removeClass("loading");
        $("#attachThreadSearchButton").removeClass("disabled");
        attachThreadChanged();
    });
}

function attachThread(cfid, patchid, closefunc) {
    browseThreads(
        (msgid) => {
            doAttachThread(cfid, patchid, msgid, !closefunc);
            if (closefunc) {
                /* We don't really care about closing it, we just reload immediately */
                closefunc();
            }
        },
        () => {
            if (closefunc) closefunc();
        },
    );
}

function detachThread(cfid, patchid, msgid) {
    if (
        confirm(
            `Are you sure you want to detach the thread with messageid "${msgid}" from this patch?`,
        )
    ) {
        $.post("/ajax/detachThread/", {
            cf: cfid,
            p: patchid,
            msg: msgid,
        })
            .success((data) => {
                location.reload();
            })
            .fail((data) => {
                alert("Failed to detach thread!");
            });
    }
}

function attachThreadChanged() {
    if ($("#attachThreadList").val() || $("#attachThreadMessageId").val()) {
        $("#doAttachThreadButton").removeClass("disabled");
    } else {
        $("#doAttachThreadButton").addClass("disabled");
    }
}

function doAttachThread(cfid, patchid, msgid, reloadonsuccess) {
    $.post("/ajax/attachThread/", {
        cf: cfid,
        p: patchid,
        msg: msgid,
    })
        .success((data) => {
            if (data !== "OK") {
                alert(data);
            }
            if (reloadonsuccess) location.reload();
            return true;
        })
        .fail((data) => {
            if (data.status === 404) {
                alert(`Message with messageid ${msgid} not found`);
            } else if (data.status === 503) {
                alert(`Failed to attach thread: ${data.responseText}`);
            } else {
                alert(`Failed to attach thread: ${data.statusText}`);
            }
            return false;
        });
}

function updateAnnotationMessages(threadid) {
    $("#annotateMessageBody").addClass("loading");
    $("#doAnnotateMessageButton").addClass("disabled");
    $.get("/ajax/getMessages", {
        t: threadid,
    })
        .success((data) => {
            sel = $("#annotateMessageList");
            sel.find("option").remove();
            sel.append('<option value="">---</option>');
            $.each(data, (i, m) => {
                sel.append(
                    `<option value="${m.msgid}">${m.from}: ${m.subj} (${m.date})</option>`,
                );
            });
        })
        .always(() => {
            $("#annotateMessageBody").removeClass("loading");
        });
}
function addAnnotation(threadid) {
    $("#annotateThreadList").find("option").remove();
    $("#annotateMessage").val("");
    $("#annotateMsgId").val("");
    $("#annotateModal").modal();
    $("#annotateThreadList").focus();
    updateAnnotationMessages(threadid);
    $("#doAnnotateMessageButton").unbind("click");
    $("#doAnnotateMessageButton").click(() => {
        const msg = $("#annotateMessage").val();
        if (msg.length >= 500) {
            alert(
                "Maximum length for an annotation is 500 characters.\nYou should probably post an actual message in the thread!",
            );
            return;
        }
        $("#doAnnotateMessageButton").addClass("disabled");
        $("#annotateMessageBody").addClass("loading");
        $.post("/ajax/annotateMessage/", {
            t: threadid,
            msgid: $.trim($("#annotateMsgId").val()),
            msg: msg,
        })
            .success((data) => {
                if (data !== "OK") {
                    alert(data);
                    $("#annotateMessageBody").removeClass("loading");
                } else {
                    $("#annotateModal").modal("hide");
                    location.reload();
                }
            })
            .fail((data) => {
                alert("Failed to annotate message");
                $("#annotateMessageBody").removeClass("loading");
            });
    });
}

function annotateMsgPicked() {
    const val = $("#annotateMessageList").val();
    if (val) {
        $("#annotateMsgId").val(val);
        annotateChanged();
    }
}

function annotateChanged() {
    /* Enable/disable the annotate button */
    if ($("#annotateMessage").val() !== "" && $("#annotateMsgId").val()) {
        $("#doAnnotateMessageButton").removeClass("disabled");
    } else {
        $("#doAnnotateMessageButton").addClass("disabled");
    }
}

function deleteAnnotation(annid) {
    if (confirm("Are you sure you want to delete this annotation?")) {
        $.post("/ajax/deleteAnnotation/", {
            id: annid,
        })
            .success((data) => {
                location.reload();
            })
            .fail((data) => {
                alert("Failed to delete annotation!");
            });
    }
}

function flagCommitted(committer) {
    $("#commitModal").modal();
    $("#committerSelect")[0].selectize.setValue(committer);
    $("#doCommitButton").unbind("click");
    $("#doCommitButton").click(() => {
        const c = $("#committerSelect").val();
        if (!c) {
            alert(
                "You need to select a committer before you can mark a patch as committed!",
            );
            return;
        }
        document.location.href = `close/committed/?c=${c}`;
    });
    return false;
}

function sortpatches(sortby) {
    const sortkey = Number.parseInt($("#id_sortkey").val());
    if (sortkey === sortby) {
        $("#id_sortkey").val(-sortby);
    } else if (-sortkey === sortby) {
        $("#id_sortkey").val(0);
    } else {
        $("#id_sortkey").val(sortby);
    }
    $("#filterform").submit();

    return false;
}

function toggleButtonCollapse(buttonId, collapseId) {
    $(`#${buttonId}`).button("toggle");
    $(`#${collapseId}`).toggleClass("in");
}

function togglePatchFilterButton(buttonId, collapseId) {
    /* Figure out if we are collapsing it */
    if ($(`#${collapseId}`).hasClass("in")) {
        /* Go back to ourselves without a querystring to reset the form, unless it's already empty */
        if (document.location.href.indexOf("?") > -1) {
            document.location.href = ".";
            return;
        }
    }

    toggleButtonCollapse(buttonId, collapseId);
}

/*
 * Upstream user search dialog
 */
function search_and_store_user() {
    $("#doSelectUserButton").unbind("click");
    $("#doSelectUserButton").click(() => {
        if (!$("#searchUserList").val()) {
            return false;
        }

        /* Create this user locally */
        $.get("/ajax/importUser/", {
            u: $("#searchUserList").val(),
        })
            .success((data) => {
                if (data === "OK") {
                    alert("User imported!");
                    $("#searchUserModal").modal("hide");
                } else {
                    alert(`Failed to import user: ${data}`);
                }
            })
            .fail((data, statustxt) => {
                alert(`Failed to import user: ${statustxt}`);
            });

        return false;
    });

    $("#searchUserModal").modal();
}

function findUsers() {
    if (!$("#searchUserSearchField").val()) {
        alert("No search term specified");
        return false;
    }
    $("#searchUserListWrap").addClass("loading");
    $("#searchUserSearchButton").addClass("disabled");
    $.get("/ajax/searchUsers/", {
        s: $("#searchUserSearchField").val(),
    })
        .success((data) => {
            sel = $("#searchUserList");
            sel.find("option").remove();
            $.each(data, (i, u) => {
                sel.append(
                    `<option value="${u.u}">${u.u} (${u.f} ${u.l})</option>`,
                );
            });
        })
        .always(() => {
            $("#searchUserListWrap").removeClass("loading");
            $("#searchUserSearchButton").removeClass("disabled");
            searchUserListChanged();
        });
    return false;
}

function searchUserListChanged() {
    if ($("#searchUserList").val()) {
        $("#doSelectUserButton").removeClass("disabled");
    } else {
        $("#doSelectUserButton").addClass("disabled");
    }
}

function addGitCheckoutToClipboard(patchId) {
    navigator.clipboard.writeText(`git remote add commitfest https://github.com/postgresql-cfbot/postgresql.git
git fetch commitfest cf/${patchId}
git checkout commitfest/cf/${patchId}
`);
}

/* Build our button callbacks */
$(document).ready(() => {
    $("button.attachThreadButton").each((i, o) => {
        const b = $(o);
        b.click(() => {
            $("#attachThreadAttachOnly").val("1");
            browseThreads((msgid, subject) => {
                b.prev().val(msgid);
                const description_field = $("#id_name");
                if (description_field.val() === "") {
                    description_field.val(subject);
                }
                return true;
            });
            return false;
        });
    });

    $(".enable-selectize").selectize({
        plugins: ["remove_button"],
        valueField: "id",
        labelField: "value",
        searchField: "value",
        onFocus: function () {
            if (this.$input.is("[multiple]")) {
                return;
            }
            this.lastValue = this.getValue();
            this.clear(false);
        },
        onBlur: function () {
            if (this.$input.is("[multiple]")) {
                return;
            }
            if (this.getValue() === "") {
                this.setValue(this.lastValue);
            }
        },
    });
});
