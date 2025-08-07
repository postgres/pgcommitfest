<div style="margin-bottom:5px;">
 <a class="btn btn-outline-secondary" href="edit/">Edit</a>

 <div class="btn-group">
  <button class="btn btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">Comment/Review</button>
  <ul class="dropdown-menu">
   <li><a class="dropdown-item" href="comment/">Comment</a></li>
   <li><a class="dropdown-item" href="review/">Review</a></li>
  </ul>
 </div>

 <div class="btn-group">
  <button class="btn btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">Change Status</button>
  <ul class="dropdown-menu">
   <li><h6 class="dropdown-header">Open statuses</h6></li>
   <li><a class="dropdown-item" href="status/review/">Needs review</a></li>
   <li><a class="dropdown-item" href="status/author/">Waiting on Author</a></li>
   <li><a class="dropdown-item" href="status/committer/">Ready for Committer</a></li>
   <li><hr class="dropdown-divider"></li>
   <li><h6 class="dropdown-header">Closed statuses</h6></li>
   <li><a class="dropdown-item" href="close/reject/" onclick="return verify_reject()">Rejected</a></li>
   <li><a class="dropdown-item" href="close/withdrawn/" onclick="return verify_withdrawn()">Withdrawn</a></li>
   <li><a class="dropdown-item" href="close/feedback/" onclick="return verify_returned()">Returned with feedback</a></li>
   <li><a class="dropdown-item" href="close/committed/" onclick="return flagCommitted({%if patch.committer%}'{{patch.committer}}'{%elif is_committer%}'{{user.username}}'{%else%}null{%endif%})">Committed</a></li>
   <li><hr class="dropdown-divider"></li>
   <li><h6 class="dropdown-header">Move to</h6></li>
   {%if not cf.is_open_regular %}
    <li>
     <a class="dropdown-item"
        href="move/?from_cf_id={{cf.id}}&to_cf_id={{cfs.open.id}}">
      Next CF: {{cfs.open.name}}</a>
    </li>
   {%endif%}
   {%if not cf.is_open_draft %}
    <li>
     <a class="dropdown-item"
        href="move/?from_cf_id={{cf.id}}&to_cf_id={{cfs.draft.id}}">
      {%if cf.draft %}
       Next Drafts:
      {%else%}
       Draft:
      {%endif%}
      {{cfs.draft.name}}</a>
    </li>
   {%endif%}
  </ul>
 </div>

 {%if request.user.is_staff%}
  <div class="btn-group">
   <button class="btn btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">Send private mail</button>
   <ul class="dropdown-menu">
    <li><a class="dropdown-item" href="send_email/?authors={{patch.id}}">Send mail to authors</a></li>
    <li><a class="dropdown-item" href="send_email/?reviewers={{patch.id}}">Send mail to reviewers</a></li>
    <li><a class="dropdown-item" href="send_email/?authors={{patch.id}}&reviewers={{patch.id}}">Send mail to authors and reviewers</a></li>
   </ul>
  </div>
 {%endif%}

</div>
