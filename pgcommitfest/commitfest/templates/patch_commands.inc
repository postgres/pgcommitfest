<div style="margin-bottom:5px;">
<a class="btn btn-default" href="edit/">Edit</a>

<div class="btn-group">
 <a class="btn btn-default dropdown-toggle" data-toggle="dropdown" href="#">Comment/Review <span class="caret"></span></a>
 <ul class="dropdown-menu">
  <li><a href="comment/">Comment</a>
  <li><a href="review/">Review</a>
 </ul>
</div>

<div class="btn-group">
 <a class="btn btn-default dropdown-toggle" data-toggle="dropdown" href="#">Change Status <span class="caret"></span></a>
 <ul class="dropdown-menu" role="menu">
  <li role="presentation" class="dropdown-header">Open statuses</li>
  <li role="presentation"><a href="status/review/">Needs review</a></li>
  <li role="presentation"><a href="status/author/">Waiting on Author</a></li>
  <li role="presentation"><a href="status/committer/">Ready for Committer</a></li>
  <li role="presentation" class="divider"></li>
  <li role="presentation" class="dropdown-header">Closed statuses</li>
  <li role="presentation"><a href="close/reject/" onclick="return verify_reject()">Rejected</a></li>
  <li role="presentation"><a href="close/withdrawn/" onclick="return verify_withdrawn()">Withdrawn</a></li>
  <li role="presentation"><a href="close/feedback/" onclick="return verify_returned()">Returned with feedback</a></li>
  <li role="presentation"><a href="close/next/?cfid={{cf.id}}" onclick="return verify_next()">Move to next CF</a></li>
  <li role="presentation"><a href="close/committed/" onclick="return flagCommitted({%if patch.committer%}'{{patch.committer}}'{%elif is_committer%}'{{user.username}}'{%else%}null{%endif%})">Committed</a></li>
 </ul>
</div>

{%if request.user.is_staff%}
<div class="btn-group">
 <a class="btn btn-default dropdown-toggle" data-toggle="dropdown" href="#">Send private mail <span class="caret"></span></a>
 <ul class="dropdown-menu">
  <li><a href="send_email/?authors={{patch.id}}">Send mail to authors</a></li>
  <li><a href="send_email/?reviewers={{patch.id}}">Send mail to reviewers</a></li>
  <li><a href="send_email/?authors={{patch.id}}&reviewers={{patch.id}}">Send mail to authors and reviewers</a></li>
 </ul>
</div>
{%endif%}

</div>
