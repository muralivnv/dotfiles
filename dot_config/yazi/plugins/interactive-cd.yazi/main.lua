local function fail(s, ...) ya.notify { title = "Zoxide", content = s:format(...), timeout = 5, level = "error" } end

local function prompt()
    return ya.input {
    title = "Change to Directory",
    position = { "center", w = 50 },
        realtime = false
    }
end

local function push_to_zoxide(target_dir)
  ya.emit("shell", {cwd = fs.cwd(), orphan=true, "zoxide add " .. ya.quote(target_dir)})
end

local function entry()
    local input, event = prompt()
    if event == 2 then
        return
    end
    if not input or input == "" then
        return
    end

    local target = input:gsub("\n$", "")
    if target ~= "" then
        push_to_zoxide(target)
        ya.emit("cd", {target, raw=true})
    end
end

return { entry = entry }

